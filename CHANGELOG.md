# Changelog

All notable changes to this project. Newest entry at the top.

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
