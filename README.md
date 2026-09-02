# Hand Gesture Control

Discrete hand gestures via your webcam trigger desktop actions on Windows 11:
media keys, hotkeys, and app/game/browser launches. No cursor control — each
fixed gesture fires one action.

## Setup

```
pip install -r requirements.txt
```

(`psutil` reads battery/AC status for the auto-close behavior; `pycaw` +
`comtypes` set exact system-volume steps via the Windows Core Audio API;
`pystray` + `Pillow` draw the system-tray status dot.)

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

**Press `Ctrl+Alt+G`** — that's the shortcut, and it toggles the app on and off.
See **[SHORTCUT.md](SHORTCUT.md)** for the full story (setup, changing the
combo, what to do when it doesn't fire).

Or start it directly:

```
python hand_gesture_control.py
```

Either way it runs **headless**: no window, just a colored dot in the system
tray (red = disarmed, green = armed). Set `settings.show_preview` to `true` in
`config.json` to get a mirrored preview window with the landmarks and current
gesture name drawn on it — useful for aiming or debugging; press **q** in that
window to quit.

Nothing fires until you **arm** it — hold the OK sign 👌 for 1.5s, see
[Arming](#arming-the-ok-sign-gesture) below.

Before the launch gestures work, fill in the `REPLACE_ME` placeholders in
`config.json` (Opera path, tab URLs, custom app path). Entries still
containing `REPLACE_ME` are skipped with a console message instead of
erroring.

## Gestures

| Gesture | Action |
|---|---|
| Fist | Mute/unmute (0.5s hold, 5s cooldown) |
| Open palm | Play/pause (2s cooldown) |
| Thumbs up / down | Volume up / down (±10%) |
| Pinky only | Next track (2s cooldown) |
| Point (index only) | Previous track (2s cooldown) |
| OK sign (thumb-index pinch, other 3 up) | **Arm / disarm** (hold 1.5s) — not a bindable action |
| Rock-on (index+pinky) | Launch Spotify |
| L-shape (thumb+index) | Opera with preset tabs |
| Three fingers (index+middle+ring) | Launch your chosen app |

## Arming (the OK-sign gesture)

The camera runs continuously, but gestures do **nothing** until you arm it, so
everyday hand movements never trigger anything by accident.

- A **system-tray icon** (bottom-right, near the clock) shows state:
  **red = disarmed, green = armed, yellow = OK-sign held but the hold hasn't
  reached the toggle threshold yet**. Right-click it > **Quit** to exit.
- Hold the **OK sign** (thumb-index pinch, other three fingers up) steadily
  for `settings.arm_hold_seconds` (default 1.5s) to toggle. The dot flips to
  green/red the instant the toggle fires, even if you're still holding the
  gesture — no more waiting on yellow to find out if it registered.
- While armed, all other gestures fire as normal.
- It **auto-disarms** after `settings.armed_timeout_seconds` (default 12s) with
  no action fired, or immediately when you hold the OK sign for 1.5s again. Each
  fired action resets the idle timer, so an active session won't cut out
  mid-use.

`ok_sign` is the arm toggle and can't be bound to an action. The Steam launch
that used to live on it (and later on `point`) is now unbound — `peace`
(index+middle) is recognized by the classifier but has no config entry, so
that's where to put it if you want it back.


### If you can't see the tray dot

Windows 11 hides every new tray icon in the overflow flyout (the `^` chevron
left of the clock) by default. Either drag it out onto the taskbar, or re-run
`make_shortcut.ps1` — it sets `IsPromoted=1` under
`HKCU\Control Panel\NotifyIconSettings` for you. Restart Explorer (or log out)
to apply.

### Running at startup

`make_shortcut.ps1` registers the app to launch in the background at every
login, plus a `Ctrl+Alt+G` listener that starts it if it's stopped and stops
it if it's running. Run once:
`powershell -ExecutionPolicy Bypass -File make_shortcut.ps1`. See
**[SHORTCUT.md](SHORTCUT.md)**.

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
- **Hold delay** (`"hold_seconds"` per gesture, falls back to
  `settings.default_hold_seconds`, default 0.35s): requires the gesture to be
  held this long before it fires the first time. Applies to every gesture by
  default so a quick pass-through shape (e.g. an open palm mid-wave) doesn't
  fire anything; `fist` overrides it to 0.5s since accidental clenches are
  worth an extra beat.
- **Per-gesture cooldown** (`"cooldown_seconds"` per gesture, falls back to
  the global `cooldown_seconds` for `"repeat"` gestures, otherwise 0): the
  minimum time between two separate fires of that gesture, even across a
  release-and-redo. `fist` uses 5s, `pinky` (next track) uses 2s.
- **Stationary-hand check** (`settings.max_hand_speed`, default 0.035):
  frame-to-frame movement of the centroid of all 21 landmarks (in
  MediaPipe's normalized 0–1 coordinates) above this is treated as "hand in
  motion" and the gesture is ignored for that frame — filters out gestures
  caught mid-wave or mid-reach. Uses the centroid rather than just the wrist
  because a "hello" wave pivots at the wrist, so the wrist point itself
  barely moves even as the fingers sweep a wide arc. Lower it if legitimate
  slow gestures get ignored; raise it if fast waves still slip through.

## Running in the background + battery-aware auto-close

Run `powershell -ExecutionPolicy Bypass -File make_shortcut.ps1` once. It
creates a Desktop shortcut plus two Startup-folder entries: the app itself
(so it runs from every login, `pythonw.exe`, no console window) and
`hotkey_listener.py`, which owns **Ctrl+Alt+G** and toggles the app on/off.
Full details in **[SHORTCUT.md](SHORTCUT.md)**.

**Camera priority**: this script always yields the webcam to any other app.
Windows keeps a log of which app is actively reading the camera right now
(the same data behind the taskbar camera-in-use icon), and every second the
script checks it — if something else has claimed the camera it releases its
own handle and waits, reacquiring automatically once that app is done. No
config needed; it just always loses the race on purpose.

While running: on battery power, the script closes itself automatically
after `settings.battery_idle_timeout_seconds` (default 300s = 5 min) with no
hand visible in frame. Plugged into AC power, it keeps running until you quit
it (tray icon > Quit, or `Ctrl+Alt+G`) — no auto-close. This is checked every
frame via `psutil.sensors_battery()`.

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
