# Handyman — hand gesture control for Windows 11

Webcam hand-gesture control tool: `hand_gesture_control.py` maps hand gestures
to actions (volume, screenshot, etc.) via `config.json`. `hotkey_listener.py`
runs at login and launches the main script on `Ctrl+Alt+G`.

## Key facts (see CHANGELOG.md for full history)

- **MediaPipe Tasks API only** — `mp.solutions` is gone in the installed
  version (0.10.35) and raises `AttributeError`. Uses
  `HandLandmarker.detect_for_video` with `hand_landmarker.task` (model file,
  tracked in git) sitting next to the script. Timestamps must use
  `time.monotonic()`, not `time.time()` (must be strictly increasing).
- **Volume**: `pycaw`/`comtypes` (Core Audio API) for exact percentage steps —
  not `pyautogui` media keys, which are locked to the OS's fixed ~2% step.
- **Battery/idle**: `psutil.sensors_battery()`.
- **Arm/disarm gating**: gestures only fire while "armed" (hold `point`
  steadily to toggle). Prevents incidental hand movement from triggering
  actions while the camera stays always-on.
- **Runs headless by default** (`settings.show_preview: false`) with a
  **system-tray icon** (`pystray` + `Pillow`, drawn as a colored dot: red =
  disarmed, green = armed). On Windows 11 new tray icons land in the hidden
  overflow flyout — `make_shortcut.ps1` sets `IsPromoted=1` in
  `HKCU\Control Panel\NotifyIconSettings` to pin it to the visible taskbar.
- **Camera sharing**: polls the Windows camera-consent registry
  (`...\CapabilityAccessManager\ConsentStore\webcam`) so it releases the
  webcam automatically when another app (Teams, Zoom, etc.) is using it.
- **Logging under `pythonw`**: no console exists, so `print()`/crashes are
  silent unless redirected. `hotkey_listener.py` redirects the launched
  script's stdout/stderr to `gesture_control.log` with `-u` (unbuffered —
  without it, Python block-buffers non-console stdout and the log looks
  stale/empty). The listener itself logs to `hotkey_listener.log`.
- `*.log` / `*.err` are gitignored (runtime artifacts, not source).

## Workflow

- **Always log changes in CHANGELOG.md** (newest entry at the top) — this is
  an established convention for this project, not optional.
