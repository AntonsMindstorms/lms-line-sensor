"""Generate the standalone Pybricks upload file."""

from pathlib import Path

from pybricks_bundle_ast import (
    adapt_ur_for_bundle,
    extract_class_module,
    extract_ur_module,
    transform_module,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
LINE_SENSOR_FILE = REPO_ROOT / "micropython" / "line_sensor.py"
VENDOR_DIR = REPO_ROOT / "micropython" / "vendor"
OUTPUT_FILE = REPO_ROOT / "micropython" / "line_sensor_pybricks.py"


def _read(path):
    return path.read_text(encoding="utf-8").strip()


def main():
    line_sensor_src = _read(LINE_SENSOR_FILE)
    base_src = (
        '"""Shared API and constants for LMS line sensor drivers."""\n\n\n'
        + extract_class_module(line_sensor_src, "BaseLineSensor")
    )
    ur_src = extract_ur_module(line_sensor_src)

    parts = [
        '"""Generated standalone Pybricks driver for the LMS line sensor.\n\n'
        "Do not edit by hand. Regenerate with:\n"
        "`python tools/generate_line_sensor_pybricks.py`\n"
        '"""',
        "__all__ = ['BaseLineSensor', 'LineSensorUR', 'uRemote', 'uRemoteError', '__version__']",
        transform_module(
            base_src, slim_base=True, omit_tagged_methods=True, strip_docstrings=True
        ),
        _read(VENDOR_DIR / "uremote_pybricks.py"),
        transform_module(
            adapt_ur_for_bundle(ur_src),
            omit_tagged_methods=True,
            strip_docstrings=True,
        ),
    ]
    OUTPUT_FILE.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
