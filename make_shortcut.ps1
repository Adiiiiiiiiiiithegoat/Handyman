# Creates three shortcuts:
#  1. Desktop: launches the gesture control script directly (pythonw, no console).
#  2. Startup folder: launches hand_gesture_control.py at login so it runs in the
#     background from boot (tray icon only, no preview) — no manual start needed.
#  3. Startup folder: launches hotkey_listener.py at login, which owns Ctrl+Alt+G
#     via the Win32 RegisterHotKey API (relaunches the app if it has exited).
# The .lnk Hotkey property is deliberately NOT used: Explorer's shortcut-hotkey
# binding proved unreliable on this machine, and a stale binding can steal
# Ctrl+Alt+G from RegisterHotKey, so this script also clears any old binding.
# Run once: powershell -ExecutionPolicy Bypass -File make_shortcut.ps1

$ProjectDir = $PSScriptRoot
$PythonExe = (Get-Command python).Source
$PythonwExe = $PythonExe -replace 'python\.exe$', 'pythonw.exe'

if (-not (Test-Path $PythonwExe)) {
    Write-Error "pythonw.exe not found next to $PythonExe"
    exit 1
}

$WshShell = New-Object -ComObject WScript.Shell

$ShortcutPath = "$env:USERPROFILE\Desktop\Hand Gesture Control.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonwExe
$Shortcut.Arguments = '"' + (Join-Path $ProjectDir "hand_gesture_control.py") + '"'
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.Hotkey = ""  # clears any old Explorer-level Ctrl+Alt+G binding
$Shortcut.Description = "Hand Gesture Control"
$Shortcut.Save()
Write-Host "Desktop shortcut created: $ShortcutPath"

$AppStartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Hand Gesture Control.lnk"
$AppStartup = $WshShell.CreateShortcut($AppStartupPath)
$AppStartup.TargetPath = $PythonwExe
$AppStartup.Arguments = '"' + (Join-Path $ProjectDir "hand_gesture_control.py") + '"'
$AppStartup.WorkingDirectory = $ProjectDir
$AppStartup.Description = "Hand Gesture Control (background, tray icon)"
$AppStartup.Save()
Write-Host "App startup shortcut created: $AppStartupPath"

$StartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Hand Gesture Hotkey Listener.lnk"
$Listener = $WshShell.CreateShortcut($StartupPath)
$Listener.TargetPath = $PythonwExe
$Listener.Arguments = '"' + (Join-Path $ProjectDir "hotkey_listener.py") + '"'
$Listener.WorkingDirectory = $ProjectDir
$Listener.Description = "Ctrl+Alt+G listener for Hand Gesture Control"
$Listener.Save()
Write-Host "Listener startup shortcut created: $StartupPath"

# Windows 11 files every NEW tray icon into the hidden overflow flyout (the "^"
# chevron) instead of the taskbar itself, so the status dot is invisible by
# default and the app looks broken. Promote it. Best-effort: the registry entry
# only exists once the icon has been shown at least once, so this is a no-op on
# a first run and takes effect after the app has started once.
$NotifyKey = 'HKCU:\Control Panel\NotifyIconSettings'
if (Test-Path $NotifyKey) {
    $promoted = 0
    Get-ChildItem $NotifyKey | ForEach-Object {
        $props = Get-ItemProperty $_.PSPath
        if ($props.ExecutablePath -like '*python*') {
            New-ItemProperty -Path $_.PSPath -Name 'IsPromoted' -Value 1 -PropertyType DWord -Force | Out-Null
            $promoted++
        }
    }
    if ($promoted -gt 0) {
        Write-Host "Promoted $promoted tray icon(s) out of the overflow flyout."
        Write-Host "Restart Explorer (or log out) if the dot is still hidden."
    } else {
        Write-Host "No tray icon registered yet - run the app once, then re-run this script."
    }
}
Write-Host "Gesture control now starts in the background at every login (tray icon, no window)."
Write-Host "Look for the red/green dot near the clock. Ctrl+Alt+G relaunches it if it has exited."
