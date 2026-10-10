"""Test setup: make the MicroPython/Pybricks-only modules importable.

The drivers import ``machine``, ``pybricks.*`` and MicroPython's ``time``
extensions, none of which exist on CPython. They are installed here once, as
thin fakes that always forward to the current test's ``Bench``.
"""

import importlib.util
import sys
import time
from pathlib import Path

import pytest

# The uRemote submodule tracks .pyc files upstream; importing it must not
# rewrite them and leave the submodule showing as modified.
sys.dont_write_bytecode = True

import fakes

REPO_ROOT = Path(__file__).resolve().parents[1]
for directory in (
    REPO_ROOT / "micropython",
    REPO_ROOT / "micropython" / "vendor" / "uRemote" / "library",  # uRemote submodule
    REPO_ROOT / "tools",
):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

if not (REPO_ROOT / "micropython" / "vendor" / "uRemote" / "library" / "uremote.py").exists():
    raise pytest.UsageError(
        "The uRemote submodule is missing. Run: git submodule update --init"
    )

# A bench must exist at import time: modules such as ``line_sensor`` are
# imported during collection. Each test then gets a fresh one (see ``bench``).
fakes.Bench.current = fakes.Bench()

sys.modules["machine"] = fakes.build_machine_module()
sys.modules.update(fakes.build_pybricks_modules())

# MicroPython's time extensions, forwarded to the current bench clock.
time.ticks_ms = lambda: fakes.Bench.current.clock.ticks_ms()
time.ticks_diff = fakes.Clock.ticks_diff
time.sleep_ms = lambda ms: fakes.Bench.current.clock.sleep_ms(ms)


def load_module(name, path):
    """Import a source file under an explicit module name."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def bench():
    """A fresh clock, wires and simulated sensor for every test."""
    fakes.Bench.current = fakes.Bench()
    return fakes.Bench.current


@pytest.fixture
def device(bench):
    """The simulated sensor firmware on the I2C bus."""
    return bench.sensor


@pytest.fixture
def desktop_uremote():
    """``usb/uremote.py`` (pyserial client), loaded under its own name."""
    return load_module("usb_uremote", REPO_ROOT / "usb" / "uremote.py")
