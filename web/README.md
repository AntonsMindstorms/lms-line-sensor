# Web dashboard

Browser console for the LMS Line Sensor over USB (Web Serial + uRemote).

## Hosted

1. Flash firmware **5.7** if needed (`firmware/`).
2. Plug the sensor into USB.
3. Open [https://linesensor.antonsmindstorms.com](https://linesensor.antonsmindstorms.com) in **Chrome** or **Edge**.
4. Choose **Connect USB** → **Line Sensor uRemote**.

Firefox and Safari do not provide Web Serial yet.

Only one program can open the USB serial port. Close this dashboard before using [`usb/`](../usb/) or a serial terminal.

## Run locally

Serve this folder over HTTP (required for Web Serial in most browsers):

```bash
cd web
python -m http.server 8000
```

Then open `http://localhost:8000`.

## What it can do

- Live bar graphs and signed position / shape
- Raw vs calibrated mode and IR emitter control
- Calibration start / load / save
- EEPROM configuration
- LED modes and per-pixel NeoPixel tests
- On-demand diagnostics (uptime, last UART/I2C commands)

Protocol details: [`../firmware/README.md`](../firmware/README.md) and [`../docs/API/lms-line-sensor-uremote-api.rst`](../docs/API/lms-line-sensor-uremote-api.rst).
