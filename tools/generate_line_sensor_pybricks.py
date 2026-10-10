"""Generate the standalone Pybricks upload file."""

import re
from pathlib import Path

from pybricks_bundle_ast import (
    adapt_ur_for_bundle,
    extract_class_module,
    extract_ur_module,
    transform_module,
    trim_uremote_for_pybricks,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
LINE_SENSOR_FILE = REPO_ROOT / "micropython" / "line_sensor.py"
UREMOTE_FILE = REPO_ROOT / "micropython" / "vendor" / "uRemote" / "library" / "uremote.py"
OUTPUT_FILE = REPO_ROOT / "micropython" / "line_sensor_pybricks.py"


def _read(path):
    return path.read_text(encoding="utf-8").strip()


def build_bundle():
    """Return the generated Pybricks driver source as a string."""
    line_sensor_src = _read(LINE_SENSOR_FILE)
    base_src = (
        '"""Shared API and constants for LMS line sensor drivers."""\n\n\n'
        + extract_class_module(line_sensor_src, "BaseLineSensor")
    )
    ur_src = extract_ur_module(line_sensor_src)
    version = re.search(r'^__version__ = (["\'].*["\'])$', line_sensor_src, re.MULTILINE)
    if version is None:
        raise ValueError("__version__ not found in line_sensor.py")

    parts = [
        '"""Generated standalone Pybricks driver for the LMS line sensor.\n\n'
        "Do not edit by hand. Regenerate with:\n"
        "`python tools/generate_line_sensor_pybricks.py`\n"
        '"""',
        "__all__ = ['BaseLineSensor', 'LineSensorUR', 'uRemote', 'uRemoteError', '__version__']",
        "__version__ = " + version.group(1),
        transform_module(
            base_src, slim_base=True, omit_tagged_methods=True, strip_docstrings=True
        ),
        trim_uremote_for_pybricks(_read(UREMOTE_FILE)),
        transform_module(
            adapt_ur_for_bundle(ur_src),
            omit_tagged_methods=True,
            strip_docstrings=True,
        ),
    ]
    return "\n\n".join(parts) + "\n"


def main():
    OUTPUT_FILE.write_text(build_bundle(), encoding="utf-8")


if __name__ == "__main__":
    main()
