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
import time

import cv2
import psutil
import pyautogui
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
MODEL_PATH = os.path.join(BASE_DIR, "hand_landmarker.task")

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
        fingers: tip above PIP joint (smaller y = higher on screen).
        """
        thumb = self._thumb_straightness_deg(lm) > 150
        others = [lm[tip].y < lm[pip].y for tip, pip in zip(FINGER_TIPS, FINGER_PIPS)]
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


def main():
    """Open the webcam and run the detect -> debounce -> cooldown -> action loop."""
    cfg = load_config(CONFIG_PATH)
    settings = cfg["settings"]
    debounce_frames = settings.get("debounce_frames", 4)
    cooldown = settings.get("cooldown_seconds", 1.2)
    battery_idle_timeout = settings.get("battery_idle_timeout_seconds", 300)

    if not os.path.exists(MODEL_PATH):
        sys.exit(f"Hand landmark model not found: {MODEL_PATH}\n"
                 "Download it from https://storage.googleapis.com/mediapipe-models/"
                 "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task "
                 "and place it next to this script.")

    cap = cv2.VideoCapture(settings.get("camera_index", 0))
    if not cap.isOpened():
        sys.exit("No webcam found. Check that the camera is connected and not in use "
                 "by another app, or change settings.camera_index in config.json.")

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
    fired_this_hold = False              # has stable_gesture already fired once?
    last_fired = {}                      # gesture name -> timestamp, for repeat cooldown
    start_time = time.time()
    last_hand_seen = time.time()         # for the on-battery idle timeout
    print("Running. Show a gesture to the camera; press 'q' in the window to quit.")
    print(f"On battery, this closes after {battery_idle_timeout}s with no hand in frame; "
          "plugged in, it runs until you press 'q'.")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Lost the camera feed; exiting.")
            break
        frame = cv2.flip(frame, 1)  # mirror for natural interaction
        mp_image = Image(image_format=ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        timestamp_ms = int((time.time() - start_time) * 1000)
        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        gesture = None
        if result.hand_landmarks:
            last_hand_seen = time.time()
            lm = result.hand_landmarks[0]
            drawing_utils.draw_landmarks(frame, lm, HandLandmarksConnections.HAND_CONNECTIONS)
            gesture = classifier.classify(lm)

        battery = psutil.sensors_battery()
        if battery and not battery.power_plugged and time.time() - last_hand_seen > battery_idle_timeout:
            print(f"No hand detected for {battery_idle_timeout}s on battery power; closing.")
            break

        # Debounce: require the same reading N frames in a row.
        streak = streak + 1 if gesture == candidate else 1
        candidate = gesture
        stable = candidate if streak >= debounce_frames else None

        if stable != stable_gesture:
            stable_gesture = stable
            fired_this_hold = False

        if stable and stable in cfg["gestures"]:
            entry = cfg["gestures"][stable]
            now = time.time()
            # Edge-triggered: fires once per hold. Gestures marked "repeat" in
            # config (e.g. volume up/down) keep refiring every cooldown while held.
            if not fired_this_hold or (entry.get("repeat") and now - last_fired.get(stable, 0) >= cooldown):
                last_fired[stable] = now
                fired_this_hold = True
                execute_action(stable, entry)

        cv2.putText(frame, gesture or "no gesture", (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0) if gesture else (0, 0, 255), 2)
        cv2.imshow("Hand Gesture Control (q to quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()


if __name__ == "__main__":
    main()
