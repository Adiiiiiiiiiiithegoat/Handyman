# The shortcut: `Ctrl` + `Alt` + `G`

**Press `Ctrl+Alt+G` to start Hand Gesture Control. Press it again to stop it.**
It's a toggle — one key combo, on and off.

There is no window. When it's running you get a **colored dot in the system
tray** (bottom-right, next to the clock):

| Dot | Meaning |
|---|---|
| 🔴 Red | Running, but **disarmed** — gestures do nothing |
| 🟡 Yellow | You're holding the OK sign; keep holding to arm |
| 🟢 Green | **Armed** — gestures fire |
| *(no dot)* | Not running. Press `Ctrl+Alt+G`. |

To actually control anything you need two steps: `Ctrl+Alt+G` to start it, then
**hold the OK sign 👌 for 1.5s** to arm it (red → green). It auto-disarms after
12 seconds of no gestures, so you re-arm with the OK sign each time you want to
use it. See [README.md](README.md) for the full gesture list.

## Other ways to start and stop it

- **Automatically at login** — after running `make_shortcut.ps1` once, it
  starts in the background every time you log in. `Ctrl+Alt+G` is for
  restarting it after you've stopped it, or for stopping it on demand.
- **Desktop shortcut** — "Hand Gesture Control" on your Desktop. Starts it
  only; it does not stop it.
- **Tray icon → right-click → Quit** — the graceful way to stop it.
- **`python hand_gesture_control.py`** in a terminal, if you want to watch the
  log output live.

## Setting it up

Run this once, from the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File make_shortcut.ps1
```

That creates three things:

1. A **Desktop shortcut** that launches the app with `pythonw.exe` (no console
   window).
2. A **Startup-folder shortcut** for the app itself, so it runs from boot.
3. A **Startup-folder shortcut for `hotkey_listener.py`** — this is the piece
   that owns `Ctrl+Alt+G`. Without it running, the hotkey does nothing.

It also tries to pin the tray dot to the visible taskbar (Windows 11 hides
every new tray icon in the `^` overflow flyout by default).

## Changing the key combo

Edit the top of `hotkey_listener.py`:

```python
MOD_CONTROL = 0x0002
MOD_ALT     = 0x0001
VK_G        = 0x47      # 'G' — any Win32 virtual-key code works
```

`VK_G` is a [Win32 virtual-key code](https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes);
for letters it's just the uppercase ASCII value (`A` = 0x41 … `Z` = 0x5A). To
add Shift, `or` in `MOD_SHIFT = 0x0004` in the `RegisterHotKey` call. Then log
out and back in (or restart the listener) to pick up the change.

## If `Ctrl+Alt+G` does nothing

1. **Check the listener is running.** It's a `pythonw.exe` process — look for
   it in Task Manager, or just check the tail of `hotkey_listener.log`: it
   should end with `Listener started, Ctrl+Alt+G registered.`
2. **Check for a conflict.** Only one process on Windows can own a given
   combo. If `hotkey_listener.log` says `RegisterHotKey FAILED, Win32 error 1409`,
   something else has already claimed `Ctrl+Alt+G` — usually an old copy of
   the listener still running, or a stale Explorer shortcut-hotkey binding.
   Kill the other process (or re-run `make_shortcut.ps1`, which clears the
   `.lnk` binding) and restart the listener.
3. **Start the listener by hand** to see it fail loudly:
   `python hotkey_listener.py`
4. **Check `gesture_control.log`** if the hotkey logs a launch but no dot
   appears — the app itself crashed on startup, and the traceback is in there.

> The listener deliberately does **not** use Explorer's built-in shortcut
> "Hotkey" property. That never registered reliably on this machine, and a
> stale binding can silently steal the combo. It calls the Win32
> `RegisterHotKey` API directly instead.
