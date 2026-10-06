"""Read live values from the line sensor over USB uRemote."""

from __future__ import annotations

import argparse
import time

from uremote import URemote, uRemoteError, select_serial_port


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        help="Serial port (for example COM5 or /dev/ttyACM0). Omit to choose interactively.",
    )
    parser.add_argument(
        "--mode",
        choices=("current", "raw", "calibrated"),
        default="current",
        help="Sensor value mode (default: keep the current mode).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.25,
        help="Seconds between readings (default: 0.25).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    if args.interval <= 0:
        raise SystemExit("--interval must be greater than zero")

    try:
        port = args.port or select_serial_port()
        print(f"Opening {port} at 115200 baud...")
        with URemote(port) as sensor:
            if args.mode == "raw":
                sensor.call("set_mode_raw")
            elif args.mode == "calibrated":
                sensor.call("set_mode_cal")

            uid = sensor.call("get_uid")
            if not isinstance(uid, bytes):
                raise uRemoteError("get_uid returned invalid data")
            print("Sensor UID:", uid.hex().upper())
            print("Press Ctrl+C to stop.\n")

            while True:
                packet = sensor.call("all")
                if not isinstance(packet, bytes) or len(packet) < 13:
                    raise uRemoteError("all returned an invalid sensor packet")
                values = list(packet[:8])
                position = round(packet[8] * 256 / 255 - 128)
                shape = "None" if packet[12] == 32 else chr(packet[12])
                print(
                    f"values={values}  position={position:4d}  "
                    f"min={packet[9]:3d}  max={packet[10]:3d}  shape={shape}",
                    flush=True,
                )
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except uRemoteError as error:
        print(f"uRemote error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

