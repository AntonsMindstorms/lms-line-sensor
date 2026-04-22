"""
Test suite for the LMS Line Sensor base API contract.

This tests the shared API surface exposed by both LineSensorI2C and LineSensorUR,
ensuring consistent method names, return types, and constant values across backends.
"""

import sys
from unittest.mock import MagicMock, patch

# Mock MicroPython imports before importing the module
sys.modules["machine"] = MagicMock()
sys.modules["time"] = MagicMock()
sys.modules["collections"] = MagicMock()
sys.modules["uremote"] = MagicMock()
sys.modules["pybricks"] = MagicMock()
sys.modules["pybricks.tools"] = MagicMock()

# Now import the module
from micropython import line_sensor


class TestBaseLineSensorConstants:
    """Test that all backends have consistent constants."""

    def test_mode_constants(self):
        """Verify MODE_* constants are defined and match across base and concrete classes."""
        assert line_sensor.BaseLineSensor.MODE_RAW == 0
        assert line_sensor.BaseLineSensor.MODE_CALIBRATED == 1
        assert line_sensor.BaseLineSensor.MODE_SAVING == 2
        assert line_sensor.BaseLineSensor.MODE_CALIBRATING == 3

        assert line_sensor.LineSensorI2C.MODE_RAW == line_sensor.BaseLineSensor.MODE_RAW
        assert (
            line_sensor.LineSensorI2C.MODE_CALIBRATED
            == line_sensor.BaseLineSensor.MODE_CALIBRATED
        )
        assert (
            line_sensor.LineSensorI2C.MODE_SAVING
            == line_sensor.BaseLineSensor.MODE_SAVING
        )
        assert (
            line_sensor.LineSensorI2C.MODE_CALIBRATING
            == line_sensor.BaseLineSensor.MODE_CALIBRATING
        )

    def test_data_index_constants(self):
        """Verify data index constants are consistent."""
        assert line_sensor.BaseLineSensor.POSITION == 8
        assert line_sensor.BaseLineSensor.MIN == 9
        assert line_sensor.BaseLineSensor.MAX == 10
        assert line_sensor.BaseLineSensor.DERIVATIVE == 11
        assert line_sensor.BaseLineSensor.SHAPE == 12
        assert line_sensor.BaseLineSensor.VALUES == -1

        assert line_sensor.LineSensorI2C.POSITION == 8
        assert line_sensor.LineSensorI2C.MIN == 9
        assert line_sensor.LineSensorI2C.MAX == 10
        assert line_sensor.LineSensorI2C.DERIVATIVE == 11
        assert line_sensor.LineSensorI2C.SHAPE == 12
        assert line_sensor.LineSensorI2C.VALUES == -1

    def test_led_mode_constants(self):
        """Verify LED mode constants are consistent."""
        assert line_sensor.BaseLineSensor.LEDS_OFF == 0
        assert line_sensor.BaseLineSensor.LEDS_VALUES == 1
        assert line_sensor.BaseLineSensor.LEDS_VALUES_INVERTED == 2
        assert line_sensor.BaseLineSensor.LEDS_POSITION == 3
        assert line_sensor.BaseLineSensor.LEDS_MAX == 4

        assert line_sensor.LineSensorI2C.LEDS_OFF == line_sensor.BaseLineSensor.LEDS_OFF
        assert (
            line_sensor.LineSensorI2C.LEDS_VALUES
            == line_sensor.BaseLineSensor.LEDS_VALUES
        )
        assert (
            line_sensor.LineSensorI2C.LEDS_POSITION
            == line_sensor.BaseLineSensor.LEDS_POSITION
        )

    def test_shape_constants(self):
        """Verify shape character constants are consistent."""
        assert line_sensor.BaseLineSensor.SHAPE_NONE == " "
        assert line_sensor.BaseLineSensor.SHAPE_STRAIGHT == "|"
        assert line_sensor.BaseLineSensor.SHAPE_T == "T"
        assert line_sensor.BaseLineSensor.SHAPE_L_LEFT == "<"
        assert line_sensor.BaseLineSensor.SHAPE_L_RIGHT == ">"
        assert line_sensor.BaseLineSensor.SHAPE_Y == "Y"

        assert (
            line_sensor.LineSensorI2C.SHAPE_NONE
            == line_sensor.BaseLineSensor.SHAPE_NONE
        )
        assert line_sensor.LineSensorI2C.SHAPE_T == line_sensor.BaseLineSensor.SHAPE_T


class TestLineSensorI2CDataProcessing:
    """Test I2C-specific data processing and return type normalization."""

    def setup_method(self):
        """Set up a mocked LineSensorI2C instance for testing."""
        # Mock I2C and Pin
        with patch("micropython.line_sensor.I2C"), patch(
            "micropython.line_sensor.Pin"
        ), patch("micropython.line_sensor.ticks_ms", return_value=0), patch(
            "micropython.line_sensor.ticks_diff", return_value=1
        ), patch.object(
            line_sensor.LineSensorI2C, "load_calibration"
        ), patch.object(
            line_sensor.LineSensorI2C, "mode_calibrated"
        ), patch.object(
            line_sensor.LineSensorI2C, "check_line_type"
        ):
            self.sensor = line_sensor.LineSensorI2C()

        # Manually set the i2c mock
        self.sensor.i2c = MagicMock()
        self.sensor.current_mode = self.sensor.MODE_CALIBRATED

    def test_position_returns_scalar(self):
        """Verify position() returns a scalar, not a list."""
        # Sensor raw data: [0..7: light values, 8: position (128=center), ...]
        self.sensor.i2c.readfrom.return_value = [
            100,
            150,
            200,
            150,
            100,
            50,
            25,
            10,
            128,
            0,
            200,
            0,
            0,
        ]
        result = self.sensor.position()
        assert isinstance(result, int), f"Expected scalar, got {type(result)}"
        assert result == 0, f"Position 128 (raw) should be 0 (offset), got {result}"

    def test_position_derivative_returns_scalar(self):
        """Verify position_derivative() returns a scalar, not a list."""
        self.sensor.i2c.readfrom.return_value = [
            100,
            150,
            200,
            150,
            100,
            50,
            25,
            10,
            128,
            0,
            200,
            128,
            0,
        ]
        result = self.sensor.derivative()
        assert isinstance(result, int), f"Expected scalar, got {type(result)}"
        assert result == 0, f"Derivative 128 (raw) should be 0 (offset), got {result}"

    def test_shape_returns_character(self):
        """Verify shape() returns a character, not a list."""
        # ASCII ord("|") = 124
        self.sensor.i2c.readfrom.return_value = [
            100,
            150,
            200,
            150,
            100,
            50,
            25,
            10,
            128,
            0,
            200,
            128,
            124,
        ]
        result = self.sensor.shape()
        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert result == "|", f"Expected shape '|', got '{result}'"

    def test_sensors_returns_list_of_8(self):
        """Verify sensors() returns a list of 8 values."""
        self.sensor.i2c.readfrom.return_value = [
            10,
            20,
            30,
            40,
            50,
            60,
            70,
            80,
            128,
            0,
            200,
            128,
            124,
        ]
        result = self.sensor.sensors()
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) == 8, f"Expected 8 values, got {len(result)}"
        assert result == [10, 20, 30, 40, 50, 60, 70, 80]

    def test_position_offset_applied(self):
        """Verify position offset (-128) is applied to raw byte."""
        # Test center position
        self.sensor.i2c.readfrom.return_value = [100] * 8 + [128] + [0] * 4
        assert self.sensor.position() == 0

        # Test left position (raw: 64, offset: 64-128 = -64)
        self.sensor.i2c.readfrom.return_value = [100] * 8 + [64] + [0] * 4
        assert self.sensor.position() == -64

        # Test right position (raw: 200, offset: 200-128 = 72)
        self.sensor.i2c.readfrom.return_value = [100] * 8 + [200] + [0] * 4
        assert self.sensor.position() == 72

    def test_derivative_offset_applied(self):
        """Verify derivative offset (-128) is applied to raw byte."""
        # Test no change
        self.sensor.i2c.readfrom.return_value = [100] * 8 + [128, 0, 200, 128] + [0]
        assert self.sensor.derivative() == 0

        # Test left movement (raw: 64, offset: -64)
        self.sensor.i2c.readfrom.return_value = [100] * 8 + [128, 0, 200, 64] + [0]
        assert self.sensor.derivative() == -64

    def test_shape_chr_conversion(self):
        """Verify SHAPE byte is converted to character."""
        # SHAPE_STRAIGHT ("|") = ord("|") = 124
        self.sensor.i2c.readfrom.return_value = [100] * 8 + [128, 0, 200, 128, 124]
        assert self.sensor.shape() == "|"

        # SHAPE_NONE (" ") = ord(" ") = 32
        self.sensor.i2c.readfrom.return_value = [100] * 8 + [128, 0, 200, 128, 32]
        assert self.sensor.shape() == " "

        # SHAPE_T ("T") = ord("T") = 84
        self.sensor.i2c.readfrom.return_value = [100] * 8 + [128, 0, 200, 128, 84]
        assert self.sensor.shape() == "T"

    def test_data_with_no_indices_returns_all_bytes(self):
        """Verify data() with no args returns all 13 raw bytes."""
        raw_data = [10, 20, 30, 40, 50, 60, 70, 80, 128, 0, 200, 128, 124]
        self.sensor.i2c.readfrom.return_value = raw_data
        result = self.sensor.data()
        assert result == raw_data, f"Expected {raw_data}, got {result}"

    def test_data_with_indices_applies_offset_and_chr(self):
        """Verify data(*indices) applies offset and chr conversion correctly."""
        self.sensor.i2c.readfrom.return_value = [
            10,
            20,
            30,
            40,
            50,
            60,
            70,
            80,
            128,
            9,
            200,
            100,
            84,
        ]

        # Request position and shape
        result = self.sensor.data(self.sensor.POSITION, self.sensor.SHAPE)
        assert result == [0, "T"], f"Expected [0, 'T'], got {result}"

    def test_black_line_value_inversion(self):
        """Verify values are inverted when black_line is True."""
        self.sensor.black_line = False
        self.sensor.i2c.readfrom.return_value = [10, 20, 30, 40, 50, 60, 70, 80] + [
            0
        ] * 5

        # Normal (white line)
        result = self.sensor.sensors()
        assert result == [10, 20, 30, 40, 50, 60, 70, 80]

        # Black line (inverted: 255 - value)
        self.sensor.black_line = True
        result = self.sensor.sensors()
        expected = [255 - v for v in [10, 20, 30, 40, 50, 60, 70, 80]]
        assert result == expected, f"Expected {expected}, got {result}"


class TestSharedAPISignatures:
    """Test that all required methods exist on base class and are callable."""

    def test_base_class_has_required_methods(self):
        """Verify BaseLineSensor defines all required abstract methods."""
        required_methods = [
            "mode_raw",
            "mode_calibrated",
            "sensors",
            "position",
            "position_derivative",
            "shape",
            "data",
            "calibrate",
            "load_calibration",
            "save_calibration",
            "ir_power",
            "leds",
        ]
        for method_name in required_methods:
            assert hasattr(
                line_sensor.BaseLineSensor, method_name
            ), f"BaseLineSensor missing method: {method_name}"

    def test_i2c_implements_all_base_methods(self):
        """Verify LineSensorI2C implements all base class methods."""
        required_methods = [
            "mode_raw",
            "mode_calibrated",
            "sensors",
            "position",
            "position_derivative",
            "shape",
            "data",
            "calibrate",
            "load_calibration",
            "save_calibration",
            "ir_power",
            "leds",
        ]
        for method_name in required_methods:
            assert hasattr(
                line_sensor.LineSensorI2C, method_name
            ), f"LineSensorI2C missing method: {method_name}"


if __name__ == "__main__":
    # Simple test runner (can also use pytest)
    import traceback

    test_classes = [
        TestBaseLineSensorConstants,
        TestLineSensorI2CDataProcessing,
        TestSharedAPISignatures,
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        test_instance = test_class()
        for method_name in dir(test_instance):
            if method_name.startswith("test_"):
                try:
                    if hasattr(test_instance, "setup_method"):
                        test_instance.setup_method()
                    method = getattr(test_instance, method_name)
                    method()
                    print(f"✓ {test_class.__name__}.{method_name}")
                    passed += 1
                except Exception as e:
                    print(f"✗ {test_class.__name__}.{method_name}")
                    traceback.print_exc()
                    failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
