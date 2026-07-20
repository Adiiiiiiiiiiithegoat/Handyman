"""Global Ctrl+Alt+G listener that launches hand_gesture_control.py.

Windows Explorer's shortcut "Hotkey" property turned out to be unreliable
on this machine (didn't register even after an Explorer restart, on two
different key combos). This instead calls the Win32 RegisterHotKey API
directly and blocks on a message loop — the same mechanism Explorer uses
internally, just not dependent on Explorer's icon-scan timing.
"""

import ctypes
import ctypes.wintypes as wintypes
import os
import subprocess
import sys

import psutil

MOD_CONTROL = 0x0002
MOD_ALT = 0x0001
VK_G = 0x47
HOTKEY_ID = 1
WM_HOTKEY = 0x0312

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(BASE_DIR, "hand_gesture_control.py")
LOG_PATH = os.path.join(BASE_DIR, "hotkey_listener.log")


def _log(message):
    """Append a timestamped line to hotkey_listener.log.

    Writes to a file instead of stdout because this runs under pythonw.exe
    with no console attached, where sys.stdout can be None and a bare
    print() would crash the listener silently.
    """
    import datetime
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {message}\n")


def _already_running():
    """True if hand_gesture_control.py is already running, to avoid piling up duplicates."""
    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmdline = proc.info["cmdline"] or []
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if any("hand_gesture_control.py" in str(part) for part in cmdline):
            return True
    return False


def _launch():
    """Start the gesture-control script with no console window.

    stdout/stderr go to gesture_control.log — under pythonw there is no
    console, so without this every print and crash traceback is lost and
    the script can die silently (seen in the wild: relaunch 10s after a
    launch, meaning the first instance was already dead).
    """
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    with open(os.path.join(BASE_DIR, "gesture_control.log"), "a", encoding="utf-8") as out:
        # -u: unbuffered. Redirected to a file, Python block-buffers stdout, so a
        # crash or startup message can sit unflushed indefinitely and the log
        # looks silent while the process is alive — useless for debugging.
        subprocess.Popen([pythonw, "-u", SCRIPT_PATH], cwd=BASE_DIR, stdout=out, stderr=out)
    _log("Ctrl+Alt+G pressed -> launched hand_gesture_control.py")


def main():
    """Register Ctrl+Alt+G and launch the gesture script each time it's pressed."""
    if not ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_G):
        _log(f"RegisterHotKey FAILED, Win32 error {ctypes.GetLastError()}")
        sys.exit(1)

    _log("Listener started, Ctrl+Alt+G registered.")
    msg = wintypes.MSG()
    try:
        while ctypes.windll.user32.GetMessageA(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID and not _already_running():
                _launch()
    finally:
        ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        _log("Listener stopped, hotkey unregistered.")


if __name__ == "__main__":
    main()
