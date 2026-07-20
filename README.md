# Hand Gesture Control

Discrete hand gestures via your webcam trigger desktop actions on Windows 11:
media keys, hotkeys, and app/game/browser launches. No cursor control — each
fixed gesture fires one action.

## Setup

```
pip install opencv-python mediapipe pyautogui psutil pycaw comtypes
```

(`psutil` reads battery/AC status for the auto-close behavior; `pycaw` +
`comtypes` set exact system-volume steps via the Windows Core Audio API.)

You also need the hand-landmark model file. Recent MediaPipe releases
(0.10.9+, including the 0.10.35 tested here) dropped the old `mp.solutions`
API in favor of the Tasks API, which loads its model from a `.task` file
instead of bundling it. Download it once into this folder:

```
curl -o hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
```

(PowerShell: `Invoke-WebRequest -Uri <url> -OutFile hand_landmarker.task`.)
The script checks for `hand_landmarker.task` next to itself and prints this
same link if it's missing.

## Run

```
python hand_gesture_control.py
```

A mirrored preview window opens with hand landmarks drawn and the current
gesture name overlaid. Press **q** in the window to quit.

Before launching gestures work, fill in the `REPLACE_ME` placeholders in
`config.json` (Steam app id, Opera path, tab URLs, custom app path). Entries
still containing `REPLACE_ME` are skipped with a console message instead of
erroring.

## Gestures

| Gesture | Action |
|---|---|
| Fist | Mute/unmute |
| Open palm | Play/pause |
| Thumbs up / down | Volume up / down (±5%) |
| Peace (index+middle) | Next track |
| Point (index only) | **Arm / disarm** (hold 3s) — not a bindable action |
| OK sign (thumb-index pinch, other 3 up) | Launch game |
| Rock-on (index+pinky) | Launch Spotify |
| L-shape (thumb+index) | Opera with preset tabs |
| Three fingers (index+middle+ring) | Launch your chosen app |

## Arming (the point gesture)

The camera runs continuously, but gestures do **nothing** until you arm it, so
everyday hand movements never trigger anything by accident.

- A **system-tray icon** (bottom-right, near the clock) shows state:
  **red = disarmed, green = armed**. Right-click it > **Quit** to exit.
- Hold the **point** gesture (index finger only) steadily for
  `settings.arm_hold_seconds` (default 3s) to toggle. Red → green on arm.
- While armed, all other gestures fire as normal.
- It **auto-disarms** after `settings.armed_timeout_seconds` (default 12s) with
  no action fired, or immediately when you hold point for 3s again. Each fired
  action resets the idle timer, so an active session won't cut out mid-use.

`point` is the arm toggle and can't be bound to an action.

By default the app runs headless (tray icon only, no webcam window) so it can
sit in the background. Set `settings.show_preview` to `true` to get the live
preview window back (with `q` to quit) — useful for aiming or debugging.

### If you can't see the tray dot

Windows 11 hides every new tray icon in the overflow flyout (the `^` chevron
left of the clock) by default. Either drag it out onto the taskbar, or re-run
`make_shortcut.ps1` — it sets `IsPromoted=1` under
`HKCU\Control Panel\NotifyIconSettings` for you. Restart Explorer (or log out)
to apply.

### Running at startup

`make_shortcut.ps1` registers the app to launch in the background at every
login (plus a `Ctrl+Alt+G` listener that relaunches it if it has exited). Run
once: `powershell -ExecutionPolicy Bypass -File make_shortcut.ps1`.

## Debounce and cooldown

- **Debounce** (`settings.debounce_frames`, default 4): a gesture must be
  classified identically for N consecutive frames before it counts. Filters
  out single-frame misreads while you move your hand.
- **Cooldown / repeat**: by default a gesture fires once per "hold" — you
  have to release it (hand relaxes, or a different gesture appears) before
  it can fire again. This stops something like open-palm play/pause from
  rapidly toggling while you hold your hand still. Add `"repeat": true` to
  a gesture's config entry to make it instead keep refiring every
  `cooldown_seconds` while held — `thumbs_up`/`thumbs_down` use this so
  holding the gesture steps the volume repeatedly.

## Running in the background + battery-aware auto-close

Run `powershell -ExecutionPolicy Bypass -File make_shortcut.ps1` once. It
creates a Desktop shortcut that launches the script with `pythonw.exe` (no
console window) bound to **Ctrl+Alt+G** — press that combo anytime to start
it without opening a terminal. Edit the `Hotkey` line in the script first if
you want a different combo.

**Camera priority**: this script always yields the webcam to any other app.
Windows keeps a log of which app is actively reading the camera right now
(the same data behind the taskbar camera-in-use icon), and every second the
script checks it — if something else has claimed the camera it releases its
own handle and waits, reacquiring automatically once that app is done. No
config needed; it just always loses the race on purpose.

While running: on battery power, the script closes itself automatically
after `settings.battery_idle_timeout_seconds` (default 300s = 5 min) with no
hand visible in frame. Plugged into AC power, it keeps running until you
press `q` — no auto-close. This is checked every frame via
`psutil.sensors_battery()`.

## Adding a new gesture

1. Add one branch in `GestureClassifier.classify()` in
   `hand_gesture_control.py` returning a new name, using the
   `(thumb, index, middle, ring, pinky)` extended-finger booleans (and/or the
   pinch distance).
2. Add an entry with that name under `"gestures"` in `config.json`. Action
   types: `media_key` (a [pyautogui key name](https://pyautogui.readthedocs.io/en/latest/keyboard.html#keyboard-keys)),
   `volume_step` (integer percent, e.g. `5` or `-5` — sets exact system
   volume via Core Audio, unlike `media_key`'s fixed ~2% OS step),
   `hotkey` (list of keys pressed together), `launch_app` (one exe path,
   folder, or URI like `spotify:` / `steam://rungameid/123`),
   `open_multiple` (list of paths/folders/apps opened one by one), or
   `open_browser_tabs` (`{"browser_path": ..., "urls": [...]}`).

No code changes are needed to *remap* an existing gesture — just edit its
config entry.

## Finding your Opera path and Steam app id

- **Opera**: usually `C:\Users\<you>\AppData\Local\Programs\Opera\opera.exe`.
  To confirm: open Opera, Task Manager → right-click the Opera process →
  *Open file location*. Or in PowerShell: `(Get-Command opera -ErrorAction SilentlyContinue).Source`.
- **Steam app id**: open the game's page on the Steam store — the number in
  the URL (`store.steampowered.com/app/`**`271590`**`/...`) is the app id.
  Put it in `steam://rungameid/<id>`.

## Why no Playwright/CDP for the browser tabs

Attaching an automation framework to a running Opera requires relaunching it
with remote debugging enabled, killing your normal browser session. Passing
URLs as plain process arguments (`opera.exe url1 url2 ...`) opens each as a
tab in a normal window with your default profile — no framework, no
disruption.

## Changelog

See `CHANGELOG.md` for the history of what's changed and why.
