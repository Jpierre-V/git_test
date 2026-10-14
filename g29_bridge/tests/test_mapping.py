import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from g29_bridge import DEFAULT_CONFIG, hat_to_dpad, map_pedal, map_steering, validate_config  # noqa: E402

STEER = {"wheel_rotation_degrees": 900, "steering_lock_degrees": 270, "deadzone": 0.0, "curve": 1.0}


class SteeringTest(unittest.TestCase):
    def test_center_is_zero(self):
        self.assertEqual(map_steering(0.0, STEER), 0.0)

    def test_full_lock_reached_at_steering_lock(self):
        self.assertAlmostEqual(map_steering(270 / 900, STEER), 1.0)
        self.assertAlmostEqual(map_steering(-270 / 900, STEER), -1.0)
        self.assertEqual(map_steering(1.0, STEER), 1.0)

    def test_deadzone_and_anti_deadzone(self):
        cfg = dict(STEER, deadzone=0.1, anti_deadzone=0.2)
        self.assertEqual(map_steering(0.02, cfg), 0.0)
        self.assertGreaterEqual(map_steering(0.04, cfg), 0.2)

    def test_invert(self):
        self.assertLess(map_steering(0.1, dict(STEER, invert=True)), 0)


class PedalTest(unittest.TestCase):
    def test_rest_and_floored(self):
        cfg = {"invert": True, "deadzone": 0.0}
        self.assertEqual(map_pedal(1.0, cfg), 0.0)
        self.assertEqual(map_pedal(-1.0, cfg), 1.0)
        self.assertAlmostEqual(map_pedal(0.0, cfg), 0.5)

    def test_deadzone(self):
        self.assertEqual(map_pedal(0.96, {"invert": True, "deadzone": 0.03}), 0.0)


class MiscTest(unittest.TestCase):
    def test_hat(self):
        self.assertEqual(hat_to_dpad((0, 0)), set())
        self.assertEqual(hat_to_dpad((1, 1)), {"DPAD_UP", "DPAD_RIGHT"})

    def test_default_config_valid(self):
        with open(DEFAULT_CONFIG) as f:
            self.assertEqual(validate_config(json.load(f)), [])

    def test_bad_button_rejected(self):
        self.assertTrue(validate_config({"steering": {"axis": 0}, "throttle": {"axis": 1},
                                         "brake": {"axis": 2}, "buttons": {"0": "Z"}}))


if __name__ == "__main__":
    unittest.main()
