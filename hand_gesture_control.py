"""Hand-gesture-controlled desktop automation for Windows 11.

Webcam frames -> MediaPipe Hands landmarks -> GestureClassifier -> action
from config.json (media keys, hotkeys, app/URI launches, browser tabs).
Quit the preview window with 'q'.
"""

import json
import math
import os
import subprocess
import sys
import threading
import time
import winreg

import cv2
import psutil
import pyautogui
import pystray
from PIL import Image as PILImage, ImageDraw
from pycaw.utils import AudioUtilities
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    HandLandmarksConnections,
    RunningMode,
)
from mediapipe.tasks.python.vision.core.image import Image, ImageFormat
from mediapipe.tasks.python.vision import drawing_utils

# pyautogui's fail-safe aborts any key press while the mouse sits in a screen
# corner — it exists to let you kill a runaway script that is *moving* the
# mouse. This app never touches the cursor, so the fail-safe only ever misfired:
# gesture_control.log shows mute/play-pause silently failing with
# "fail-safe triggered" whenever the pointer was parked in a corner.
pyautogui.FAILSAFE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
MODEL_PATH = os.path.join(BASE_DIR, "hand_landmarker.task")

WEBCAM_CONSENT_STORE = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"
)
CAMERA_CHECK_INTERVAL = 1.0  # seconds between "does another app want the camera" checks

# MediaPipe landmark indices.
WRIST = 0
THUMB_MCP, THUMB_IP, THUMB_TIP = 2, 3, 4
INDEX_TIP, INDEX_MCP = 8, 5
FINGER_TIPS = (8, 12, 16, 20)   # index, middle, ring, pinky
FINGER_PIPS = (6, 10, 14, 18)


def load_config(path):
    """Load and sanity-check config.json; exit with a clear message on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        sys.exit(f"Config not found: {path}\nCreate config.json next to this script (see README.md).")
    except json.JSONDecodeError as e:
        sys.exit(f"config.json is not valid JSON: {e}")
    if "gestures" not in cfg or not isinstance(cfg["gestures"], dict):
        sys.exit('config.json must contain a "gestures" object.')
    cfg.setdefault("settings", {})
    return cfg


class GestureClassifier:
    """Maps 21 MediaPipe hand landmarks to a named gesture string (or None).

    Add a new gesture: add one branch in classify() returning a new name,
    then map that name to an action in config.json.
    """

    def __init__(self, pinch_threshold=0.06):
        """pinch_threshold: max normalized thumb-tip/index-tip distance for a pinch."""
        self.pinch_threshold = pinch_threshold

    @staticmethod
    def _dist(a, b):
        """Euclidean distance between two normalized landmarks."""
        return math.hypot(a.x - b.x, a.y - b.y)

    @staticmethod
    def _thumb_straightness_deg(lm):
        """Angle (degrees) at the thumb IP joint between the MCP and TIP segments.

        Near 180 = thumb held straight (extended). A folded thumb (as in a
        fist, where it curls over the palm) bends sharply at this joint, so
        this is far more reliable than comparing tip distance to a knuckle,
        which stays ambiguous when a curled thumb still ends up far from it.
        """
        mcp, ip, tip = lm[THUMB_MCP], lm[THUMB_IP], lm[THUMB_TIP]
        v1 = (mcp.x - ip.x, mcp.y - ip.y)
        v2 = (tip.x - ip.x, tip.y - ip.y)
        mag1, mag2 = math.hypot(*v1), math.hypot(*v2)
        if mag1 == 0 or mag2 == 0:
            return 180.0
        cos_angle = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (mag1 * mag2)))
        return math.degrees(math.acos(cos_angle))

    def _finger_states(self, lm):
        """Return (thumb, index, middle, ring, pinky) extended booleans.

        Thumb: straight at the IP joint (see _thumb_straightness_deg). Other
        fingers: tip farther from the wrist than the PIP joint. This is
        rotation-invariant — a tip-above-PIP y-check breaks on a sideways
        fist (thumbs up/down), where curled tips can sit above their PIPs
        on screen and misread as extended.
        """
        wrist = lm[WRIST]
        thumb = self._thumb_straightness_deg(lm) > 150
        others = [self._dist(lm[tip], wrist) > self._dist(lm[pip], wrist)
                  for tip, pip in zip(FINGER_TIPS, FINGER_PIPS)]
        return (thumb, *others)

    def classify(self, lm):
        """Return the gesture name for these landmarks, or None if unrecognized."""
        thumb, index, middle, ring, pinky = self._finger_states(lm)
        pinch = self._dist(lm[THUMB_TIP], lm[INDEX_TIP]) < self.pinch_threshold

        if pinch and middle and ring and pinky:
            return "ok_sign"
        if thumb and index and middle and ring and pinky:
            return "open_palm"
        if not any((thumb, index, middle, ring, pinky)):
            return "fist"
        if thumb and not any((index, middle, ring, pinky)):
            return "thumbs_up" if lm[THUMB_TIP].y < lm[WRIST].y else "thumbs_down"
        if pinky and not any((thumb, index, middle, ring)):
            return "pinky"
        if index and pinky and not middle and not ring:
            return "rock_on"  # thumb ignored: rock-on and "spiderman" both count
        if index and middle and ring and not thumb and not pinky:
            return "three_fingers"
        if index and middle and not any((thumb, ring, pinky)):
            return "peace"
        if index and not any((thumb, middle, ring, pinky)):
            return "point"
        if thumb and index and not any((middle, ring, pinky)):
            return "l_shape"
        return None


def _camera_claimed_by_others():
    """True if some app other than us is actively reading the webcam right now.

    Reads the same per-app usage log that drives Windows' own camera-in-use
    taskbar icon (Settings > Privacy > Camera). Each app gets a subkey with
    a LastUsedTimeStop value that's zero while it's still using the camera.
    Letting Windows be the source of truth means this yields to *any* other
    app (Teams, Zoom, the Camera app, ...) without hardcoding names.
    """
    own = os.path.normcase(sys.executable)
    claimed = False
    for sub in ("", r"\NonPackaged"):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, WEBCAM_CONSENT_STORE + sub)
        except OSError:
            continue
        with key:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                if name == "NonPackaged" or os.path.normcase(name.replace("#", "\\")) == own:
                    continue
                try:
                    with winreg.OpenKey(key, name) as entry:
                        stop, _ = winreg.QueryValueEx(entry, "LastUsedTimeStop")
                    if stop == 0:
                        claimed = True
                except OSError:
                    continue
    return claimed


_volume_interface = None  # lazy-initialized COM handle; avoids startup cost if unused


def _get_volume_interface():
    """Return the Core Audio endpoint volume interface, creating it on first use.

    Windows media keys step system volume by a fixed OS-level amount (~2%)
    that pyautogui can't resize. Setting an exact step size means talking
    to the Core Audio API directly instead of pressing volumeup/volumedown.
    """
    global _volume_interface
    if _volume_interface is None:
        _volume_interface = AudioUtilities.GetSpeakers().EndpointVolume
    return _volume_interface


def execute_action(name, entry):
    """Execute one configured gesture entry. Prints instead of crashing on bad config."""
    action, value = entry.get("action"), entry.get("value")
    if "REPLACE_ME" in json.dumps(value):
        print(f"[{name}] skipped: fill in the REPLACE_ME placeholder in config.json first.")
        return
    try:
        if action == "media_key":
            pyautogui.press(value)
        elif action == "volume_step":
            vol = _get_volume_interface()
            current = vol.GetMasterVolumeLevelScalar()
            vol.SetMasterVolumeLevelScalar(min(1.0, max(0.0, current + value / 100.0)), None)
        elif action == "hotkey":
            pyautogui.hotkey(*value)
        elif action == "launch_app":
            os.startfile(value)
        elif action == "open_multiple":
            for item in value:
                os.startfile(item)
        elif action == "open_browser_tabs":
            subprocess.Popen([value["browser_path"], *value["urls"]])
        else:
            print(f"[{name}] unknown action type in config: {action!r}")
            return
        print(f"[{name}] -> {entry.get('label', action)}")
    except Exception as e:  # bad path, missing exe, etc. — keep the loop alive
        print(f"[{name}] action failed: {e}")


def should_fire(entry, now, stable_since, last_fired, fired_this_hold,
                default_hold_seconds, default_cooldown):
    """True if this gesture entry should fire on this frame.

    Three independent gates, all of which must pass:
      - hold:     held (stable) for "hold_seconds", else settings.default_hold_seconds
      - cooldown: "cooldown_seconds" since the last fire. Defaults to the global
                  cooldown for "repeat" gestures and to 0 otherwise, so a plain
                  gesture can be re-fired immediately after a deliberate redo
                  unless it opts in to a gap (e.g. fist: 5s between mutes).
      - edge:     fires once per hold, unless "repeat" is set (volume up/down),
                  which keeps refiring every cooldown while the gesture is held.
    """
    hold_required = entry.get("hold_seconds", default_hold_seconds)
    gesture_cooldown = entry.get("cooldown_seconds",
                                 default_cooldown if entry.get("repeat") else 0)
    return (now - stable_since >= hold_required
            and now - last_fired >= gesture_cooldown
            and (not fired_this_hold or bool(entry.get("repeat"))))


_STATE_COLORS = {
    "armed": (34, 200, 34),
    "disarmed": (210, 40, 40),
    "arming": (230, 200, 0),  # holding the arm/disarm gesture, toggle not fired yet
}


class TrayIndicator:
    """System-tray (taskbar notification area) dot: green = armed, red = disarmed,
    yellow = arm/disarm gesture currently held but the toggle hasn't fired yet.

    pystray owns the tray icon on its own thread; the main loop just calls
    set_state(). Right-click > Quit sets stop_event so the main loop exits
    cleanly — the reliable way to stop it when running headless at startup
    (no console, and the preview window may be hidden).
    """

    def __init__(self):
        self.stop_event = threading.Event()
        self._state = "disarmed"
        self._icon = pystray.Icon(
            "hand_gesture_control",
            self._image("disarmed"),
            "Hand Gesture Control — disarmed",
            menu=pystray.Menu(pystray.MenuItem("Quit", self._quit)),
        )
        threading.Thread(target=self._icon.run, daemon=True).start()

    @staticmethod
    def _image(state):
        img = PILImage.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse((8, 8, 56, 56), fill=_STATE_COLORS[state])
        return img

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        self._icon.icon = self._image(state)
        self._icon.title = "Hand Gesture Control — " + state

    def _quit(self, icon, _item):
        self.stop_event.set()
        icon.stop()

    def close(self):
        self._icon.stop()


def main():
    """Open the webcam and run the detect -> debounce -> cooldown -> action loop.

    Yields the camera to any other app that wants it (see
    _camera_claimed_by_others): this app has the lowest priority for the
    webcam, so it releases its handle whenever something else claims it and
    reacquires once that app is done, instead of holding it exclusively.
    """
    cfg = load_config(CONFIG_PATH)
    settings = cfg["settings"]
    debounce_frames = settings.get("debounce_frames", 4)
    cooldown = settings.get("cooldown_seconds", 1.2)
    default_hold_seconds = settings.get("default_hold_seconds", 0.35)
    max_hand_speed = settings.get("max_hand_speed", 0.035)  # normalized-coords landmark-centroid movement/frame above which a gesture is ignored as "in motion"
    battery_idle_timeout = settings.get("battery_idle_timeout_seconds", 300)
    camera_index = settings.get("camera_index", 0)
    arm_hold = settings.get("arm_hold_seconds", 3)
    armed_timeout = settings.get("armed_timeout_seconds", 12)
    show_preview = settings.get("show_preview", False)  # off = background, tray icon only
    arm_gesture = "ok_sign"  # holding this gesture toggles armed; not bindable to an action

    if not os.path.exists(MODEL_PATH):
        sys.exit(f"Hand landmark model not found: {MODEL_PATH}\n"
                 "Download it from https://storage.googleapis.com/mediapipe-models/"
                 "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task "
                 "and place it next to this script.")

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        cap.release()
        if _camera_claimed_by_others():
            cap = None  # another app has it; the main loop will wait its turn
        else:
            sys.exit("No webcam found. Check that the camera is connected, "
                     "or change settings.camera_index in config.json.")

    classifier = GestureClassifier(settings.get("pinch_threshold", 0.06))
    landmarker = HandLandmarker.create_from_options(HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    ))

    candidate, streak = None, 0          # debounce state
    stable_gesture = None                # last gesture confirmed by debounce
    stable_since = 0.0                   # when stable_gesture last changed, for gestures.<name>.hold_seconds
    fired_this_hold = False              # has stable_gesture already fired once?
    last_fired = {}                      # gesture name -> timestamp, for repeat cooldown
    armed = False                        # actions only fire while armed
    armed_at = 0.0                       # for the idle auto-disarm timeout
    arm_hold_start = None                # when the current continuous arm-gesture hold began
    toggle_consumed = False              # arm/disarm fired for this hold; wait for release
    prev_center = None                   # last frame's landmark centroid (x, y), for the stationary-hand check
    tray = TrayIndicator()
    start_time = time.monotonic()  # detect_for_video needs strictly increasing timestamps; wall clock can step backward
    last_hand_seen = time.time()         # for the on-battery idle timeout
    last_camera_check = 0.0
    print("Running. Tray icon (bottom-right, near the clock): red = disarmed, "
          f"green = armed, yellow = {arm_gesture} gesture detected.")
    print(f"Hold the {arm_gesture} gesture for {arm_hold}s to arm. Quit via the tray icon's "
          "right-click menu" + (" or 'q' in the preview window." if show_preview else "."))
    print("Yields the camera automatically whenever another app needs it.")
    print(f"On battery, this closes after {battery_idle_timeout}s with no hand in frame; "
          "plugged in, it runs until you quit.")

    while True:
        now_mono = time.monotonic()
        if now_mono - last_camera_check >= CAMERA_CHECK_INTERVAL:
            last_camera_check = now_mono
            claimed = _camera_claimed_by_others()
            if claimed and cap is not None:
                cap.release()
                cap = None
                cv2.destroyAllWindows()
                print("Another app wants the camera; pausing until it's free.")
            elif not claimed and cap is None:
                candidate_cap = cv2.VideoCapture(camera_index)
                if candidate_cap.isOpened():
                    cap = candidate_cap
                    print("Camera free again; resuming.")
                else:
                    candidate_cap.release()

        if cap is None:
            if tray.stop_event.is_set():  # tray > Quit must work while paused too
                break
            time.sleep(0.2)
            continue

        ok, frame = cap.read()
        if not ok:
            cap.release()
            cap = None
            continue  # likely lost the race with another app; next check will sort it out
        frame = cv2.flip(frame, 1)  # mirror for natural interaction
        mp_image = Image(image_format=ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        timestamp_ms = int((time.monotonic() - start_time) * 1000)
        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        gesture = None
        if result.hand_landmarks:
            last_hand_seen = time.time()
            lm = result.hand_landmarks[0]
            if show_preview:
                drawing_utils.draw_landmarks(frame, lm, HandLandmarksConnections.HAND_CONNECTIONS)
            # Centroid of all 21 landmarks, not just the wrist: a "hello" wave
            # rotates mostly at the wrist, so the wrist point itself barely
            # moves even though the fingers sweep a wide arc — the wrist alone
            # misses that motion entirely. The centroid shifts with either a
            # translating hand or a rotating/waving one.
            cx = sum(p.x for p in lm) / len(lm)
            cy = sum(p.y for p in lm) / len(lm)
            moving = prev_center is not None and math.hypot(cx - prev_center[0], cy - prev_center[1]) > max_hand_speed
            prev_center = (cx, cy)
            if not moving:  # ignore gestures while the hand is still in transit (e.g. mid-wave)
                gesture = classifier.classify(lm)
        else:
            prev_center = None

        battery = psutil.sensors_battery()
        if battery and not battery.power_plugged and time.time() - last_hand_seen > battery_idle_timeout:
            print(f"No hand detected for {battery_idle_timeout}s on battery power; closing.")
            break

        # Debounce: require the same reading N frames in a row.
        streak = streak + 1 if gesture == candidate else 1
        candidate = gesture
        stable = candidate if streak >= debounce_frames else None

        now = time.time()

        if stable != stable_gesture:
            stable_gesture = stable
            fired_this_hold = False
            stable_since = now

        # Arm/disarm: hold arm_gesture steadily for arm_hold seconds to toggle.
        # toggle_consumed makes one hold flip the state exactly once; you must
        # release the gesture before it can toggle again.
        if stable == arm_gesture:
            if not toggle_consumed:
                tray.set_state("arming")
            if arm_hold_start is None:
                arm_hold_start = now
            elif not toggle_consumed and now - arm_hold_start >= arm_hold:
                armed = not armed
                armed_at = now
                toggle_consumed = True
                tray.set_state("armed" if armed else "disarmed")  # reflect the flip immediately, even mid-hold
                print("Armed — gestures active." if armed else "Disarmed.")
        else:
            arm_hold_start = None
            toggle_consumed = False
            tray.set_state("armed" if armed else "disarmed")

        # Auto-disarm after armed_timeout seconds with no action fired.
        if armed and now - armed_at >= armed_timeout:
            armed = False
            tray.set_state("disarmed")
            print(f"Auto-disarmed after {armed_timeout}s idle.")

        if armed and stable and stable in cfg["gestures"]:
            entry = cfg["gestures"][stable]
            if should_fire(entry, now, stable_since, last_fired.get(stable, 0),
                           fired_this_hold, default_hold_seconds, cooldown):
                last_fired[stable] = now
                fired_this_hold = True
                armed_at = now  # activity keeps the arm alive; idle disarms
                execute_action(stable, entry)

        if show_preview:
            status = "ARMED" if armed else f"hold {arm_gesture} {arm_hold}s to arm"
            cv2.putText(frame, f"{gesture or 'no gesture'}  [{status}]", (10, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0) if armed else (0, 0, 255), 2)
            cv2.imshow("Hand Gesture Control (q to quit)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        else:
            time.sleep(0.005)  # yield without a preview window; the tray icon is the only UI

        if tray.stop_event.is_set():  # tray > Quit
            break

    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    tray.close()
    landmarker.close()


if __name__ == "__main__":
    main()
