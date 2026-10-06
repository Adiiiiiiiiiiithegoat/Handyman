# Handyman: plan

## Gesture control
- [x] Webcam gesture classifier on the MediaPipe Tasks API
- [x] Media keys, exact ±10% volume via pycaw, app and browser launches
- [x] Arm/disarm with a 1.5 s OK-sign hold and 12 s idle auto-disarm
- [x] Debounce, hold delay, per-gesture cooldown and stationary-hand check
- [x] Fire gate (should_fire) covered by test_gestures.py

## Desktop integration
- [x] Headless run with a red/green/yellow system-tray dot
- [x] Ctrl+Alt+G toggle listener registered at login by make_shortcut.ps1
- [x] Releases the webcam while Teams/Zoom are using it
- [x] Battery auto-close after 5 min with no hand in frame

## Open items
- [ ] Fill in the 4 REPLACE_ME launch entries in config.json (Opera path, tabs, custom app)
- [ ] Fix CLAUDE.md: it still says arming is a held point gesture, it's the OK sign
- [ ] Record a 30 s gesture demo video
