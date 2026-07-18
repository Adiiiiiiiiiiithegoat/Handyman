# Creates a desktop shortcut that launches the gesture control script silently
# (pythonw.exe, no console window) and binds it to a keyboard shortcut.
# Run once: powershell -ExecutionPolicy Bypass -File make_shortcut.ps1

$ProjectDir = $PSScriptRoot
$PythonExe = (Get-Command python).Source
$PythonwExe = $PythonExe -replace 'python\.exe$', 'pythonw.exe'

if (-not (Test-Path $PythonwExe)) {
    Write-Error "pythonw.exe not found next to $PythonExe"
    exit 1
}

$ShortcutPath = "$env:USERPROFILE\Desktop\Hand Gesture Control.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonwExe
$Shortcut.Arguments = '"' + (Join-Path $ProjectDir "hand_gesture_control.py") + '"'
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.Hotkey = "CTRL+ALT+G"  # change here if you want a different combo
$Shortcut.Description = "Hand Gesture Control"
$Shortcut.Save()

Write-Host "Shortcut created: $ShortcutPath"
Write-Host "Press Ctrl+Alt+G anytime to launch it (works even if the shortcut isn't focused)."
