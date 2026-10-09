"""LineSensorI2C and LineSensorUR promise one high-level API (README, "API overview")."""

import inspect

import pytest

from line_sensor import LineSensorI2C, LineSensorUR

# The table in README.md, plus the helpers every example uses.
SHARED_API = [
    "position",
    "derivative",
    "shape",
    "sensors",
    "position_derivative_shape",
    "data",
    "mode_raw",
    "mode_calibrated",
    "calibrate",
    "ir_power",
    "set_emitter",
    "leds",
    "neopixel",
    "blackline",
    "save_calibration",
    "load_calibration",
    "start_calibration",
    "is_calibrated",
    "get_cal_min",
    "get_cal_max",
    "set_cal_min",
    "set_cal_max",
    "set_calibration",
    "get_config",
    "get_configuration",
    "set_cal_duration",
    "set_load_cal_startup",
    "set_shape_threshold_black",
    "set_ir_emitter_startup",
    "load_config",
    "save_config",
    "get_uid",
    "uid_hex",
]


def parameter_names(function):
    return list(inspect.signature(function).parameters)


@pytest.mark.parametrize("name", SHARED_API)
@pytest.mark.parametrize("backend", [LineSensorI2C, LineSensorUR])
def test_backend_provides_the_shared_method(backend, name):
    assert callable(getattr(backend, name, None)), "%s lacks %s()" % (backend.__name__, name)


@pytest.mark.parametrize("name", SHARED_API)
def test_shared_methods_take_the_same_leading_arguments(name):
    i2c = parameter_names(getattr(LineSensorI2C, name))
    ur = parameter_names(getattr(LineSensorUR, name))
    shared = min(len(i2c), len(ur))
    assert i2c[:shared] == ur[:shared]


@pytest.mark.parametrize("name", ["set_emitter", "ir_power"])
def test_emitter_alias_has_the_same_argument_name(name):
    assert parameter_names(getattr(LineSensorI2C, name)) == ["self", "power"]
    assert parameter_names(getattr(LineSensorUR, name)) == ["self", "power"]


def test_documented_calibrate_signature():
    """README: ``calibrate(duration=5)``; UR defaults to the sensor's own setting."""
    assert inspect.signature(LineSensorI2C.calibrate).parameters["duration"].default == 5
    assert inspect.signature(LineSensorUR.calibrate).parameters["duration"].default is None
