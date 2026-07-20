# Changelog

All notable changes to this project. Newest entry at the top.

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
