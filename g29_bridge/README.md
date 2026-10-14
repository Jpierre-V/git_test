# G29 Bridge for Star Wars: Galactic Racer

Star Wars: Galactic Racer has no steering wheel support. This tool makes your
Logitech G29 look like an Xbox 360 controller, which the game does support.

| G29 | Becomes |
|---|---|
| Steering wheel | Left stick (left/right) |
| Gas pedal | Right trigger (RT) |
| Brake pedal | Left trigger (LT) |
| Face buttons, paddles, D-pad | Xbox buttons (set in `config.json`) |

Windows only (ViGEmBus is a Windows driver).

## Setup (about 10 minutes)

1. Install **Logitech G HUB** and plug in the G29 (switch on the wheel set to **PS3**).
2. Install the **ViGEmBus** driver: <https://github.com/nefarius/ViGEmBus/releases> (run the `.exe`, reboot if asked).
3. Install **Python 3.10+** from python.org (tick "Add python.exe to PATH").
4. In this folder, run: `pip install -r requirements.txt`
5. Run: `python g29_bridge.py`, then start the game.

Leave the window open while you play. Ctrl+C stops it.

## If an input is wrong

Run `python g29_bridge.py --detect`, move the wheel / press pedals / buttons,
and note the numbers that change. Put those numbers in `config.json`.

## Tuning (`config.json`)

- `steering_lock_degrees` — how far you turn for full lock. Lower = twitchier. Default 270.
- `deadzone` — ignore tiny movements around center.
- `anti_deadzone` — try `0.1`–`0.2` if small turns do nothing in-game.
- `curve` — above `1.0` = gentler near center, below `1.0` = sharper.
- `clutch.maps_to` — `"none"`, `"LT"` or `"RT"`.
- `buttons` — G29 button number → `A B X Y LEFT_SHOULDER RIGHT_SHOULDER LEFT_THUMB RIGHT_THUMB BACK START GUIDE DPAD_*`.

## Known limits

- **No real force feedback.** The game doesn't send any. In G HUB, turn on
  **centering spring** so the wheel self-centers.
- **The game may see two controllers** (the wheel + the virtual pad). If inputs
  fight, disable the wheel in Steam → Settings → Controller, or use HidHide to
  hide the wheel from the game.
- Virtual controllers are the same tech DS4Windows uses, but use online play at your own risk.
