"""Tests for the LMS Line Sensor package and standalone Pybricks artifact."""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
MICROPYTHON_DIR = REPO_ROOT / "micropython"
if str(MICROPYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(MICROPYTHON_DIR))

machine_module = types.ModuleType("machine")
machine_module.I2C = MagicMock()
machine_module.Pin = MagicMock()
sys.modules["machine"] = machine_module

time_module = types.ModuleType("time")
time_module.sleep = MagicMock()
time_module.ticks_ms = MagicMock(return_value=0)
time_module.ticks_diff = MagicMock(return_value=1)
time_module.sleep_ms = MagicMock()
sys.modules["time"] = time_module

pybricks_module = types.ModuleType("pybricks")
pybricks_tools = types.ModuleType("pybricks.tools")
pybricks_tools.wait = MagicMock()
pybricks_tools.StopWatch = MagicMock()
pybricks_iodevices = types.ModuleType("pybricks.iodevices")
pybricks_iodevices.UARTDevice = MagicMock()
pybricks_parameters = types.ModuleType("pybricks.parameters")
pybricks_parameters.Port = MagicMock()
sys.modules["pybricks"] = pybricks_module
sys.modules["pybricks.tools"] = pybricks_tools
sys.modules["pybricks.iodevices"] = pybricks_iodevices
sys.modules["pybricks.parameters"] = pybricks_parameters

import line_sensor
import line_sensor_pybricks


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
        with patch.object(line_sensor.LineSensorI2C, "load_calibration"), patch.object(
            line_sensor.LineSensorI2C, "mode_calibrated"
        ), patch.object(line_sensor.LineSensorI2C, "check_line_type"):
            self.sensor = line_sensor.LineSensorI2C()
        self.sensor.i2c = MagicMock()
        self.sensor.current_mode = self.sensor.MODE_CALIBRATED
        self.sensor.black_line = False

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
        """Verify sensors() returns a tuple of 8 values."""
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
        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        assert len(result) == 8, f"Expected 8 values, got {len(result)}"
        assert result == (10, 20, 30, 40, 50, 60, 70, 80)

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
        assert result == tuple(raw_data), f"Expected {tuple(raw_data)}, got {result}"

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
        assert result == (0, "T"), f"Expected (0, 'T'), got {result}"

    def test_black_line_value_inversion(self):
        """Verify values are inverted when black_line is True."""
        self.sensor.black_line = False
        self.sensor.i2c.readfrom.return_value = [10, 20, 30, 40, 50, 60, 70, 80] + [
            0
        ] * 5

        # Normal (white line)
        result = self.sensor.sensors()
        assert result == (10, 20, 30, 40, 50, 60, 70, 80)

        # Black line (inverted: 255 - value)
        self.sensor.black_line = True
        result = self.sensor.sensors()
        expected = tuple(255 - v for v in [10, 20, 30, 40, 50, 60, 70, 80])
        assert result == expected, f"Expected {expected}, got {result}"


class TestPackageLayout:
    """Verify the split package and standalone Pybricks file expose expected symbols."""

    def test_package_exports_main_classes(self):
        assert hasattr(line_sensor, "BaseLineSensor")
        assert hasattr(line_sensor, "LineSensorI2C")
        assert hasattr(line_sensor, "LineSensorUR")

    def test_pybricks_standalone_exports_line_sensor_ur(self):
        assert hasattr(line_sensor_pybricks, "LineSensorUR")
        assert hasattr(line_sensor_pybricks, "uRemote")
        assert hasattr(line_sensor_pybricks, "uRemoteError")


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
        TestPackageLayout,
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
