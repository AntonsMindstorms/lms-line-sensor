"""Generate the standalone Pybricks upload file."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = Path(__file__).resolve().parent / "pybricks_bundle"
VENDOR_DIR = REPO_ROOT / "micropython" / "vendor"
OUTPUT_FILE = REPO_ROOT / "micropython" / "line_sensor_pybricks.py"


def _read(path):
    return path.read_text(encoding="utf-8").strip()


def main():
    parts = [
        '"""Generated standalone Pybricks driver for the LMS line sensor.\n\n'
        "Do not edit by hand. Regenerate with:\n"
        "`python tools/generate_line_sensor_pybricks.py`\n"
        '"""',
        "__all__ = ['BaseLineSensor', 'LineSensorUR', 'uRemote', 'uRemoteError', '__version__']",
        _read(BUNDLE_DIR / "base.py"),
        _read(VENDOR_DIR / "uremote_pybricks.py"),
        _read(BUNDLE_DIR / "ur.py"),
    ]
    OUTPUT_FILE.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
