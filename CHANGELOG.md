# Changelog

All notable changes to this project. Newest entry at the top.

## 2026-09-02 — Debug pass: pyautogui fail-safe, dead tray Quit, docs

- **Media keys silently failed whenever the mouse was parked in a screen
  corner.** pyautogui's fail-safe aborts any input call in that state — it
  exists to let you kill a runaway script that is *moving* the cursor, which
  this app never does. `gesture_control.log` had nine
  `[fist]/[open_palm] action failed: PyAutoGUI fail-safe triggered` lines from
  real use. Now sets `pyautogui.FAILSAFE = False` at import.
- **Tray > Quit did nothing while the camera was yielded to another app.**
  The `cap is None` branch `continue`d straight past the `tray.stop_event`
  check at the bottom of the loop, so during a Teams/Zoom call the app could
  not be quit at all — it hung until the other app released the camera. The
  pause branch now checks `stop_event` too.
- **`show_preview` shipped as `true`** while the README, `CLAUDE.md` and
  `make_shortcut.ps1`'s login-startup design all assumed headless — so a
  stray webcam window popped up at every login. Set to `false` to match.
- **`open_palm` play/pause double-fired** (3–4 consecutive fires per hold in
  the log): with no `cooldown_seconds` a single-frame classifier dropout reset
  the hold and re-armed it. Given `cooldown_seconds: 2`, matching
  `pinky`/`point`.
- **`pystray` and `Pillow` were missing from the README's install line** even
  though both are hard imports — a fresh clone died on `ImportError`. Added
  `requirements.txt` and pointed the README at it.
- The fire gate (hold / cooldown / edge-vs-repeat) moved out of `main()` into
  a pure `should_fire()` so it's testable; `test_gestures.py` gained
  `run_fire_gate()` covering all three gates. No behavior change.
- **New `SHORTCUT.md`**: what `Ctrl+Alt+G` does, the tray dot colors, the
  three shortcuts `make_shortcut.ps1` creates, how to change the key combo,
  and what to check when the hotkey doesn't fire.
- README: `Ctrl+Alt+G` is now documented up front in "Run". Corrected two
  stale claims — the Desktop shortcut is *not* bound to `Ctrl+Alt+G`
  (`make_shortcut.ps1` deliberately clears that `.lnk` binding and hands the
  combo to `hotkey_listener.py`), and the hotkey toggles rather than
  "relaunches it if it has exited".

## 2026-07-26 — Ctrl+Alt+G toggles instead of only launching

- `hotkey_listener.py`: pressing the hotkey while `hand_gesture_control.py` is
  running now terminates it; previously the press was swallowed (the duplicate
  guard just ignored it) and the only way to stop the script was the tray
  menu. `_already_running()` → `_running_proc()` returning the process so it
  can be killed.

## 2026-07-25 — Volume step ±5% → ±10%

- `thumbs_up`/`thumbs_down` `value` 5 → 10. Repeat firing meant reaching a
  usable volume took a long hold; 10% gets there in half the frames.

## 2026-07-25 — Faster arm hold, previous track on `point`

- `settings.arm_hold_seconds` 3 → 1.5. The 3s hold was tuned to be
  hard to trigger accidentally, but the OK sign is distinctive enough that
  1.5s doesn't misfire in practice and makes arming feel less sluggish.
- `point` (index only) now sends `prevtrack` (previous track, 2s cooldown to
  match `pinky`/next track). The Steam launch placeholder it held is dropped
  rather than relocated — `peace` is classified but unbound if it's wanted
  back.

## 2026-07-21 — Fix stationary-hand check missing wave motion

- The stationary-hand check (previous entry below) tracked only the wrist
  landmark, but a "hello" wave rotates mostly at the wrist joint itself — the
  wrist point barely moves even though the fingers sweep a wide arc, so fast
  waves slipped through undetected and still fired open-palm play/pause.
  Now tracks the centroid of all 21 landmarks instead, which moves with
  either hand translation or wrist-pivoted rotation.

## 2026-07-21 — Motion gating, per-gesture cooldowns, arm gesture moved to OK-sign

- **Stationary-hand check**: a gesture is now ignored on any frame where the
  wrist moves more than `settings.max_hand_speed` (default 0.035, normalized
  coords) since the last frame. Fixes gestures firing off a wave or reach
  passing through a recognizable shape (e.g. open palm mid-wave triggering
  play/pause).
- **Default hold delay for every gesture**: `hold_seconds` now falls back to
  `settings.default_hold_seconds` (default 0.35s) instead of 0, so *every*
  gesture needs a brief stable hold before firing, not just ones with an
  explicit override. `fist` keeps its longer 0.5s override.
- **Per-gesture cooldown**: new `"cooldown_seconds"` per gesture applies even
  to non-repeat gestures now — it's the minimum gap between two separate
  fires, including release-then-redo (previously only repeat gestures like
  volume respected a cooldown; a plain edge-triggered gesture could refire
  instantly on release). `fist` set to 5s, `pinky` (next track) set to 2s.
- **Next track moved from `peace` to `pinky`-only** (classifier: pinky
  extended, all other fingers curled) — `peace` was too easy to trigger
  by accident; new `"pinky"` config entry.
- **Arm/disarm gesture moved from `point` to `ok_sign`** (thumb-index pinch,
  other three fingers up) — more reliable to hold steadily than a bare index
  point. `point` is no longer reserved and now runs the Steam-launch action
  that used to live on `ok_sign`.
- **Tray-icon bug fix**: the dot used to stay yellow ("arming") even after
  the hold crossed the toggle threshold, only flipping to green/red once you
  released the gesture — so there was no way to tell mid-hold whether arming
  had actually registered. It now flips immediately at the moment of toggle.
- `TrayIndicator` state renamed `"pointing"` → `"arming"` to match (no longer
  tied to a specific gesture name).

## 2026-07-21 — Per-gesture hold delay to filter accidental triggers

- New `"hold_seconds"` field on a gesture's `config.json` entry: the gesture
  must be held this long before it fires for the first time (repeat refires
  are unaffected). `fist` now defaults to `0.5`, so a brief, accidental
  clench doesn't mute audio — mirrors the hold-to-arm pattern already used
  for the `point` gesture.
- Tray dot now has a third color: **yellow, while the point gesture is being
  held** (mid-hold, whether or not it crosses the arm/disarm toggle
  threshold), on top of the existing red = disarmed / green = armed. Lets you
  confirm the classifier is actually seeing "point" without waiting for the
  arm/disarm flip.
- `TrayIndicator.set_armed(bool)` replaced with `set_state(str)` taking
  `"armed" | "disarmed" | "pointing"`.

## 2026-07-19 — Arm/disarm gating, tray icon, background auto-start

- Gestures no longer fire whenever the camera sees them. The app now runs in a
  disarmed state by default; hold the **point** gesture (index only) steadily
  for `settings.arm_hold_seconds` (default 3s) to arm, and hold it again to
  disarm. This keeps the camera always-on without day-to-day hand movements
  triggering actions.
- While armed, gestures auto-disarm after `settings.armed_timeout_seconds`
  (default 12s) with no action fired; each fired action resets that idle timer.
- Added `TrayIndicator`, a **system-tray (taskbar notification area) icon**:
  red = disarmed, green = armed, right-click > Quit to exit. Uses `pystray`
  (icon on its own daemon thread) + `Pillow` (draws the colored dot). Quit sets
  a `stop_event` the main loop checks — the reliable way to stop it when running
  headless. (An earlier stdlib-`tkinter` floating dot was replaced with this
  because "on the taskbar" specifically meant the tray, not a floating window.)
- The app now runs **headless by default** (tray icon only, no preview window)
  so it can sit in the background. New `settings.show_preview` (default
  `false`) brings the live webcam window + `q`-to-quit back for aiming/debugging.
- **Auto-start at login**: `make_shortcut.ps1` now also creates a Startup-folder
  shortcut for `hand_gesture_control.py` itself, so it launches in the
  background at boot with no manual step. The existing `Ctrl+Alt+G` listener is
  kept as a relaunch trigger (e.g. after the on-battery idle close).
- **Unbound `point` from the screenshot action** (removed its `config.json`
  entry); it's now the arm/disarm toggle and can't be mapped to an action. The
  classifier still recognizes `point` — only its config binding changed.
- New dependencies: `pystray`, `Pillow`.

### Follow-up: the tray icon was invisible (Windows 11 overflow)

- The icon was being created correctly all along — Windows 11 files every *new*
  tray icon into the hidden overflow flyout (the "^" chevron) rather than the
  taskbar, so it looked like nothing had happened. Confirmed via
  `HKCU\Control Panel\NotifyIconSettings`, where our entry existed with the
  right tooltip but no `IsPromoted` value. Setting `IsPromoted=1` (+ an Explorer
  restart) puts the dot on the taskbar itself. `make_shortcut.ps1` now does this
  automatically as a best-effort step.
- Fixed a debugging blind spot that made this hard to diagnose: `hotkey_listener.py`
  redirects the app's stdout to `gesture_control.log`, but without `-u` Python
  block-buffers stdout when it isn't a console, so the log stayed empty (showing
  yesterday's output) while the process ran fine. Launch now passes `-u`.
- Fixed an `Image` name collision: `from PIL import Image` was shadowed by
  MediaPipe's `Image` (imported later), crashing tray icon creation with
  `AttributeError: type object 'Image' has no attribute 'new'`. PIL is now
  imported as `PILImage`.

## 2026-07-19 — Camera yields to other apps automatically

- The script no longer holds the webcam exclusively. It polls the Windows
  camera-consent registry (`...\CapabilityAccessManager\ConsentStore\webcam`,
  the same per-app usage log behind the taskbar camera-in-use icon) once a
  second; if any other app has an entry with `LastUsedTimeStop == 0` (still
  reading the camera), this script releases its own `VideoCapture` handle
  and waits, reopening it once that entry clears. No hardcoded app list —
  works for Teams, Zoom, the Camera app, or anything else. Prompted by
  wanting to leave this running full-time without it fighting other apps
  (e.g. a video call) for the camera.
- Startup no longer hard-exits if the camera is simply busy at launch —
  only if it's unavailable *and* nothing else is claiming it (genuinely no
  camera present).

## 2026-07-19 — Ctrl+Alt+G fixed: listener auto-start at login

- Ctrl+Alt+G was dead because `hotkey_listener.py` wasn't running — it had
  only ever been started manually and didn't survive a reboot. `make_shortcut.ps1`
  now also creates a Startup-folder shortcut (`shell:startup`) that runs the
  listener via `pythonw` at every login, and clears the old Explorer-level
  `Ctrl+Alt+G` binding on the desktop shortcut, which could steal the combo
  from the listener's `RegisterHotKey`. Ran it, restarted the listener; log
  confirms the hotkey registered.

## 2026-07-19 — Thumbs-up detection fix, silent-crash logging

- Fixed intermittent thumbs-up/thumbs-down misses: finger curl was detected
  by "tip above PIP joint in screen-y", which only works for an upright
  hand. In a thumbs-up the fist is rotated ~90°, so curled fingertips often
  sit slightly above their PIPs on screen and misread as extended, making
  the frame classify as no-gesture and resetting the debounce streak.
  Extension is now rotation-invariant: tip farther from the wrist than the
  PIP joint. Added a regression test with real sideways-fist geometry.
- Switched the `detect_for_video` timestamp source from `time.time()` to
  `time.monotonic()` — MediaPipe requires strictly increasing timestamps,
  and the wall clock can step backward (NTP sync), which would kill the loop.
- `hotkey_listener.py` now redirects the launched script's stdout/stderr to
  `gesture_control.log`. Under `pythonw` there is no console, so crashes and
  exit messages (e.g. "No webcam found") were invisible — the listener log
  showed a relaunch 10s after a launch, i.e. the first instance had already
  died silently.

## 2026-07-18 — Battery-aware auto-close, precise volume steps, background launch

- Added an idle/battery watchdog in `main()`: if no hand has been visible in
  frame for `settings.battery_idle_timeout_seconds` (default 300s) **and**
  the laptop is running on battery, the script exits cleanly. Plugged into
  AC power, it runs indefinitely until you press `q`. Uses `psutil.sensors_battery()`.
- Replaced `thumbs_up`/`thumbs_down` volume control: was `media_key`
  (`volumeup`/`volumedown`), which steps system volume by a fixed OS-level
  amount (~2%) that can't be resized. Switched to a new `volume_step`
  action type that sets the exact system volume via the Core Audio API
  (`pycaw`), so each gesture now moves volume by a precise 5%.
- Added `make_shortcut.ps1`: creates a Desktop shortcut that launches the
  script with `pythonw.exe` (no console window) and binds it to `Ctrl+Alt+G`
  via Windows' native shortcut-hotkey support. Run once:
  `powershell -ExecutionPolicy Bypass -File make_shortcut.ps1`.
- New dependencies: `psutil`, `pycaw`, `comtypes`.
- Created this changelog.

## (same session) — Gesture classification and refire-behavior fixes

- Fixed thumb detection: the old check (tip farther from the index knuckle
  than the IP joint) misread a closed fist as `thumbs_up`/`thumbs_down`.
  Replaced with a joint-angle check at the thumb's IP joint — near 180° means
  the thumb is held straight (extended); a fist bends it sharply.
- Fixed a bug where holding a gesture steady (e.g. open palm) kept
  re-triggering its action every `cooldown_seconds`, causing rapid
  play/pause toggling. Gestures are now edge-triggered by default — one
  fire per hold, requiring the gesture to release before firing again.
  Added an opt-in `"repeat": true` config flag for gestures that should
  keep refiring while held (used by the volume gestures).
- Added `test_gestures.py`, a small assertion-based smoke test covering the
  gesture branch table and the thumb-straightness check.

## (same session) — MediaPipe Tasks API migration

- The installed MediaPipe version (0.10.35, current for Python 3.13) no
  longer ships the legacy `mp.solutions.hands` API the script was built
  against — it crashed with `AttributeError: module 'mediapipe' has no
  attribute 'solutions'`.
- Rewrote hand detection to use `mediapipe.tasks.python.vision.HandLandmarker`
  (video-mode, via `detect_for_video`) and landmark drawing via
  `mediapipe.tasks.python.vision.drawing_utils`.
- Downloaded the required model file, `hand_landmarker.task`, into the
  project folder (not bundled with the pip package under the new API).
  Script now checks for it on startup and prints the download link if missing.

## (same session) — Initial build

- Built `hand_gesture_control.py`: webcam capture (OpenCV) → MediaPipe hand
  landmarks → `GestureClassifier` (finger-state based) → config-driven
  action execution (`pyautogui` for media keys/hotkeys, `os.startfile`/
  `subprocess` for launching apps, games, and browser tabs).
  Mirrored live preview window with landmarks and gesture name overlay,
  quits on `q`.
- Ten gestures mapped: fist (mute), open palm (play/pause), thumbs up/down
  (volume), peace (next track), point (screenshot), OK sign (launch game),
  rock-on (launch Spotify), L-shape (Opera with preset tabs), three fingers
  (launch a custom app).
- Debounce (default 4 consecutive frames) and cooldown (default 1.2s) logic,
  both configurable in `config.json`.
- Built `config.json` with placeholder (`REPLACE_ME`) values for
  user-specific paths/URLs/IDs, and `README.md` covering setup, the
  debounce/cooldown model, how to add a gesture, and why the browser-tabs
  action uses plain `subprocess.Popen` instead of Playwright/CDP.
