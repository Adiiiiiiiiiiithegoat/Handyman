"""Smoke tests: GestureClassifier's branch table, and should_fire's hold/cooldown gates."""
from types import SimpleNamespace as P

import hand_gesture_control as h


def make_lm(pinch):
    """21 fake landmarks; index tip placed far from thumb tip unless pinching."""
    pts = [P(x=0.0, y=0.0) for _ in range(21)]
    if not pinch:
        pts[h.INDEX_TIP] = P(x=1.0, y=0.0)
    return pts


def run():
    """Assert every gesture branch returns its expected name."""
    c = h.GestureClassifier()
    cases = {
        (False, False, False, False, False): "fist",
        (True, True, True, True, True): "open_palm",
        (False, True, True, False, False): "peace",
        (False, True, False, False, False): "point",
        (True, True, False, False, False): "l_shape",
        (False, True, False, False, True): "rock_on",
        (False, True, True, True, False): "three_fingers",
    }
    for states, expected in cases.items():
        c._finger_states = lambda lm, s=states: s
        assert c.classify(make_lm(pinch=False)) == expected, (states, expected)

    c._finger_states = lambda lm: (True, False, True, True, True)
    assert c.classify(make_lm(pinch=True)) == "ok_sign"

    c._finger_states = lambda lm: (True, False, False, False, False)
    up = make_lm(pinch=False)
    up[h.WRIST], up[h.THUMB_TIP] = P(x=0.0, y=0.5), P(x=0.0, y=0.1)
    assert c.classify(up) == "thumbs_up"
    down = make_lm(pinch=False)
    down[h.WRIST], down[h.THUMB_TIP] = P(x=0.0, y=0.5), P(x=0.0, y=0.9)
    assert c.classify(down) == "thumbs_down"

    # Thumb folded over the palm (as in a fist) must read as NOT extended,
    # even though the tip still ends up far from the index knuckle.
    fist_lm = make_lm(pinch=False)
    fist_lm[h.THUMB_MCP] = P(x=0.5, y=0.5)
    fist_lm[h.THUMB_IP] = P(x=0.6, y=0.45)
    fist_lm[h.THUMB_TIP] = P(x=0.55, y=0.6)  # sharp bend at IP, not straight
    assert c._thumb_straightness_deg(fist_lm) < 150

    # Regression: real thumbs-up geometry — fist rotated sideways, so curled
    # fingertips sit slightly ABOVE their PIP joints on screen. The old
    # tip.y < pip.y check misread them as extended and dropped the gesture.
    c2 = h.GestureClassifier()
    side = make_lm(pinch=False)
    side[h.WRIST] = P(x=0.5, y=0.5)
    side[h.THUMB_MCP] = P(x=0.45, y=0.42)
    side[h.THUMB_IP] = P(x=0.45, y=0.35)
    side[h.THUMB_TIP] = P(x=0.45, y=0.28)  # straight thumb pointing up
    for tip, pip in zip(h.FINGER_TIPS, h.FINGER_PIPS):
        side[pip] = P(x=0.30, y=0.50)
        side[tip] = P(x=0.38, y=0.46)  # curled back toward wrist, above PIP on screen
    assert c2._finger_states(side) == (True, False, False, False, False), c2._finger_states(side)
    assert c2.classify(side) == "thumbs_up"

    straight_lm = make_lm(pinch=False)
    straight_lm[h.THUMB_MCP] = P(x=0.5, y=0.5)
    straight_lm[h.THUMB_IP] = P(x=0.5, y=0.4)
    straight_lm[h.THUMB_TIP] = P(x=0.5, y=0.3)  # colinear, straight thumb
    assert c._thumb_straightness_deg(straight_lm) > 150
    print("ALL GESTURE CHECKS PASS")


def run_fire_gate():
    """Assert should_fire's hold / cooldown / edge-vs-repeat gates."""
    HOLD, COOL = 0.35, 1.2

    def fire(entry, now, stable_since=0.0, last_fired=0.0, fired_this_hold=False):
        return h.should_fire(entry, now, stable_since, last_fired,
                             fired_this_hold, HOLD, COOL)

    plain = {"action": "media_key", "value": "playpause"}
    # Hold gate: must be stable for default_hold_seconds before the first fire.
    assert not fire(plain, now=0.2)
    assert fire(plain, now=0.5)
    # Edge gate: one fire per hold for a non-repeat gesture.
    assert not fire(plain, now=5.0, fired_this_hold=True)
    # ...but a fresh hold (fired_this_hold reset) fires again, no cooldown by default.
    assert fire(plain, now=5.0, stable_since=4.0, last_fired=4.9)

    repeat = {"action": "volume_step", "value": 10, "repeat": True}
    # Repeat gate: refires while held, but only once per global cooldown.
    assert not fire(repeat, now=1.0, last_fired=0.5, fired_this_hold=True)
    assert fire(repeat, now=2.0, last_fired=0.5, fired_this_hold=True)

    # Per-gesture cooldown gates a *non-repeat* gesture across release-and-redo
    # (regression: fist re-muting instantly on a second clench).
    fist = {"action": "media_key", "value": "volumemute",
            "hold_seconds": 0.5, "cooldown_seconds": 5}
    assert not fire(fist, now=10.4, stable_since=10.0, last_fired=10.0)  # held 0.4 < 0.5
    assert not fire(fist, now=12.0, stable_since=11.0, last_fired=10.0)  # 2s < 5s cooldown
    assert fire(fist, now=16.0, stable_since=15.0, last_fired=10.0)
    print("ALL FIRE-GATE CHECKS PASS")


if __name__ == "__main__":
    run()
    run_fire_gate()
