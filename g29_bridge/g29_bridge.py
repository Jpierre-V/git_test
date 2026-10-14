"""G29 -> virtual Xbox 360 controller bridge.

Reads a Logitech G29 wheel and drives a virtual Xbox 360 pad (via ViGEmBus),
so games without wheel support (e.g. Star Wars: Galactic Racer) see a normal
controller: steering -> left stick X, gas -> RT, brake -> LT, buttons -> pad.

Usage:
    python g29_bridge.py              # run the bridge
    python g29_bridge.py --detect     # print live axis/button/hat numbers
    python g29_bridge.py --config my.json
"""

import argparse
import json
import math
import os
import sys
import time

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

PAD_BUTTONS = {
    "A", "B", "X", "Y", "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_THUMB",
    "RIGHT_THUMB", "BACK", "START", "GUIDE",
    "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
}
TRIGGER_TARGETS = {"LT", "RT", "none"}


# --- Pure mapping math (tested in tests/test_mapping.py) ---------------------

def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def map_steering(raw, cfg):
    """Wheel axis (-1..1 over full rotation) -> stick X (-1..1)."""
    if cfg.get("invert"):
        raw = -raw
    # Reach full stick deflection at steering_lock_degrees instead of the full
    # 900 degrees, so you don't have to spin the wheel lock to lock.
    scale = cfg.get("wheel_rotation_degrees", 900) / max(1.0, cfg.get("steering_lock_degrees", 270))
    x = clamp(raw * scale, -1.0, 1.0)

    mag = abs(x)
    deadzone = cfg.get("deadzone", 0.0)
    if mag <= deadzone:
        return 0.0
    mag = (mag - deadzone) / (1.0 - deadzone)
    mag = mag ** cfg.get("curve", 1.0)
    # Games apply their own stick deadzone; anti_deadzone skips past it so
    # small wheel movements still register.
    anti = cfg.get("anti_deadzone", 0.0)
    mag = anti + (1.0 - anti) * mag
    return math.copysign(clamp(mag, 0.0, 1.0), x)


def map_pedal(raw, cfg):
    """Pedal axis (-1..1) -> trigger (0..1). G29 pedals rest at +1, so invert."""
    value = (1.0 - raw) / 2.0 if cfg.get("invert", True) else (raw + 1.0) / 2.0
    deadzone = cfg.get("deadzone", 0.0)
    if value <= deadzone:
        return 0.0
    return clamp((value - deadzone) / (1.0 - deadzone), 0.0, 1.0)


def hat_to_dpad(hat):
    """(x, y) hat tuple -> set of DPAD_* names."""
    x, y = hat
    pressed = set()
    if y > 0:
        pressed.add("DPAD_UP")
    if y < 0:
        pressed.add("DPAD_DOWN")
    if x < 0:
        pressed.add("DPAD_LEFT")
    if x > 0:
        pressed.add("DPAD_RIGHT")
    return pressed


def validate_config(cfg):
    errors = []
    for name in ("steering", "throttle", "brake"):
        if name not in cfg or "axis" not in cfg[name]:
            errors.append(f"'{name}.axis' is missing")
    clutch_target = cfg.get("clutch", {}).get("maps_to", "none")
    if clutch_target not in TRIGGER_TARGETS:
        errors.append(f"clutch.maps_to must be one of {sorted(TRIGGER_TARGETS)}")
    for idx, target in cfg.get("buttons", {}).items():
        if not str(idx).isdigit():
            errors.append(f"button index '{idx}' is not a number")
        if target not in PAD_BUTTONS:
            errors.append(f"button {idx} -> '{target}' is not one of {sorted(PAD_BUTTONS)}")
    steering = cfg.get("steering", {})
    if steering.get("deadzone", 0.0) >= 1.0 or steering.get("curve", 1.0) <= 0:
        errors.append("steering.deadzone must be < 1 and steering.curve > 0")
    return errors


def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    errors = validate_config(cfg)
    if errors:
        sys.exit("Config errors in %s:\n  - %s" % (path, "\n  - ".join(errors)))
    return cfg


# --- Hardware side ----------------------------------------------------------

def open_wheel(pygame, name_hint):
    pygame.joystick.init()
    count = pygame.joystick.get_count()
    if count == 0:
        sys.exit("No controllers found. Plug in the G29 (PS3 mode switch) and install Logitech G HUB.")
    joysticks = [pygame.joystick.Joystick(i) for i in range(count)]
    for js in joysticks:
        if name_hint.lower() in js.get_name().lower():
            return js
    names = ", ".join(js.get_name() for js in joysticks)
    sys.exit(f"No device matching '{name_hint}'. Found: {names}. Edit wheel_name_contains in config.json.")


def detect(pygame, cfg):
    js = open_wheel(pygame, cfg.get("wheel_name_contains", "G29"))
    print(f"Reading '{js.get_name()}': {js.get_numaxes()} axes, "
          f"{js.get_numbuttons()} buttons, {js.get_numhats()} hats. Ctrl+C to stop.")
    try:
        while True:
            pygame.event.pump()
            axes = " ".join(f"a{i}={js.get_axis(i):+.2f}" for i in range(js.get_numaxes()))
            buttons = [str(i) for i in range(js.get_numbuttons()) if js.get_button(i)]
            hats = " ".join(f"h{i}={js.get_hat(i)}" for i in range(js.get_numhats()))
            print(f"\r{axes} | buttons: {','.join(buttons) or '-':<12} | {hats}   ", end="", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print()


def run(pygame, cfg):
    try:
        import vgamepad as vg
    except Exception as exc:  # vgamepad raises if the ViGEmBus driver is missing
        sys.exit(f"Could not load vgamepad ({exc}). Install ViGEmBus, then: pip install -r requirements.txt")

    js = open_wheel(pygame, cfg.get("wheel_name_contains", "G29"))
    pad = vg.VX360Gamepad()

    if cfg.get("forward_rumble", True):
        def on_rumble(client, target, large_motor, small_motor, led_number, user_data):
            # Works only if SDL exposes rumble for the wheel; otherwise a no-op.
            js.rumble(large_motor / 255.0, small_motor / 255.0, 200)
        pad.register_notification(callback_function=on_rumble)

    button_map = {int(k): getattr(vg.XUSB_BUTTON, "XUSB_GAMEPAD_" + v)
                  for k, v in cfg.get("buttons", {}).items()}
    dpad_buttons = {name: getattr(vg.XUSB_BUTTON, "XUSB_GAMEPAD_" + name)
                    for name in ("DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT")}
    hat_index = cfg.get("dpad_hat", 0)
    clutch_cfg = cfg.get("clutch", {})
    clutch_target = clutch_cfg.get("maps_to", "none")
    period = 1.0 / cfg.get("poll_hz", 250)

    print(f"Bridging '{js.get_name()}' -> virtual Xbox 360 controller. Ctrl+C to stop.")
    try:
        while True:
            pygame.event.pump()

            steer = map_steering(js.get_axis(cfg["steering"]["axis"]), cfg["steering"])
            gas = map_pedal(js.get_axis(cfg["throttle"]["axis"]), cfg["throttle"])
            brake = map_pedal(js.get_axis(cfg["brake"]["axis"]), cfg["brake"])
            if clutch_target != "none" and clutch_cfg.get("axis", -1) < js.get_numaxes():
                clutch = map_pedal(js.get_axis(clutch_cfg["axis"]), clutch_cfg)
                if clutch_target == "RT":
                    gas = max(gas, clutch)
                else:
                    brake = max(brake, clutch)

            pad.left_joystick_float(x_value_float=steer, y_value_float=0.0)
            pad.right_trigger_float(value_float=gas)
            pad.left_trigger_float(value_float=brake)

            for idx, xbtn in button_map.items():
                if idx < js.get_numbuttons() and js.get_button(idx):
                    pad.press_button(button=xbtn)
                else:
                    pad.release_button(button=xbtn)

            if hat_index < js.get_numhats():
                held = hat_to_dpad(js.get_hat(hat_index))
                for name, xbtn in dpad_buttons.items():
                    (pad.press_button if name in held else pad.release_button)(button=xbtn)

            pad.update()
            time.sleep(period)
    except KeyboardInterrupt:
        pad.reset()
        pad.update()
        print("\nStopped.")


def main():
    parser = argparse.ArgumentParser(description="Use a Logitech G29 as an Xbox 360 controller.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to config.json")
    parser.add_argument("--detect", action="store_true", help="print live wheel inputs to find axis/button numbers")
    args = parser.parse_args()

    cfg = load_config(args.config)
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")  # keep reading while the game has focus
    import pygame
    pygame.init()
    try:
        detect(pygame, cfg) if args.detect else run(pygame, cfg)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
