"use strict";

const PREAMBLE = [0x3c, 0x24, 0x4d, 0x55]; // <$MU
const TYPES = { bytes: 0x41, bool: 0x42, number: 0x4e, string: 0x53 };
const encoder = new TextEncoder();
const decoder = new TextDecoder();

class URemoteSerial {
  constructor() {
    this.port = null;
    this.reader = null;
    this.writer = null;
    this.running = false;
    this.buffer = [];
    this.pending = new Map();
    this.disconnectHandler = null;
  }

  async connect() {
    if (!("serial" in navigator)) {
      throw new Error("Web Serial is not available. Use Chrome or Edge on HTTPS or localhost.");
    }
    this.port = await navigator.serial.requestPort();
    await this.port.open({ baudRate: 115200, bufferSize: 1024 });
    this.reader = this.port.readable.getReader();
    this.writer = this.port.writable.getWriter();
    this.running = true;
    this.readLoop();
  }

  async disconnect() {
    this.running = false;
    if (this.reader) {
      try { await this.reader.cancel(); } catch (_) {}
      this.reader.releaseLock();
      this.reader = null;
    }
    if (this.writer) {
      try { await this.writer.close(); } catch (_) {}
      this.writer.releaseLock();
      this.writer = null;
    }
    if (this.port) {
      try { await this.port.close(); } catch (_) {}
      this.port = null;
    }
    this.rejectAll(new Error("USB disconnected"));
  }

  async readLoop() {
    try {
      while (this.running && this.reader) {
        const { value, done } = await this.reader.read();
        if (done) break;
        if (value) {
          this.buffer.push(...value);
          this.parseFrames();
        }
      }
    } catch (error) {
      if (this.running) this.disconnectHandler?.(error);
    } finally {
      if (this.running) this.disconnectHandler?.(new Error("USB connection closed"));
    }
  }

  parseFrames() {
    while (this.buffer.length > 0) {
      const length = this.buffer[0];
      if (length < 5 || length > 255) {
        this.buffer.shift();
        continue;
      }
      if (this.buffer.length < length + 1) return;
      const frame = this.buffer.splice(0, length + 1).slice(1);
      if (!PREAMBLE.every((byte, index) => frame[index] === byte)) continue;
      this.handleFrame(frame.slice(PREAMBLE.length));
    }
  }

  handleFrame(payload) {
    const header = payload[0];
    const status = header >> 5;
    const commandLength = header & 0x1f;
    const command = decoder.decode(Uint8Array.from(payload.slice(1, 1 + commandLength)));
    const args = [];
    let cursor = 1 + commandLength;
    while (cursor < payload.length) {
      const type = payload[cursor++];
      const length = payload[cursor++];
      const bytes = Uint8Array.from(payload.slice(cursor, cursor + length));
      cursor += length;
      if (type === TYPES.bytes) args.push(bytes);
      else if (type === TYPES.bool) args.push(bytes[0] !== 0);
      else if (type === TYPES.number) args.push(Number(decoder.decode(bytes)));
      else args.push(decoder.decode(bytes));
    }

    const queue = this.pending.get(command);
    const request = queue?.shift();
    if (!request) return;
    if (queue.length === 0) this.pending.delete(command);
    if (status === 0) request.resolve(args);
    else request.reject(new Error(String(args[0] ?? `${command} failed`)));
  }

  encodeArgument(value) {
    if (value instanceof Uint8Array || Array.isArray(value)) {
      return { type: TYPES.bytes, data: Uint8Array.from(value) };
    }
    if (typeof value === "boolean") {
      return { type: TYPES.bool, data: Uint8Array.of(value ? 1 : 0) };
    }
    if (typeof value === "number") {
      return { type: TYPES.number, data: encoder.encode(String(Math.trunc(value))) };
    }
    return { type: TYPES.string, data: encoder.encode(String(value)) };
  }

  async call(command, ...values) {
    if (!this.writer) throw new Error("Connect the sensor first");
    const commandBytes = encoder.encode(command);
    if (commandBytes.length < 1 || commandBytes.length > 31) throw new Error("Invalid command name");
    const args = values.map(value => this.encodeArgument(value));
    const length = PREAMBLE.length + 1 + commandBytes.length +
      args.reduce((sum, arg) => sum + 2 + arg.data.length, 0);
    if (length > 255) throw new Error("uRemote frame is too large");

    const frame = new Uint8Array(length + 1);
    let cursor = 0;
    frame[cursor++] = length;
    frame.set(PREAMBLE, cursor); cursor += PREAMBLE.length;
    frame[cursor++] = commandBytes.length;
    frame.set(commandBytes, cursor); cursor += commandBytes.length;
    for (const arg of args) {
      frame[cursor++] = arg.type;
      frame[cursor++] = arg.data.length;
      frame.set(arg.data, cursor); cursor += arg.data.length;
    }

    const reply = new Promise((resolve, reject) => {
      const queue = this.pending.get(command) ?? [];
      const timeout = setTimeout(() => {
        const index = queue.findIndex(item => item.resolve === wrappedResolve);
        if (index >= 0) queue.splice(index, 1);
        if (queue.length === 0) this.pending.delete(command);
        reject(new Error(`${command} timed out`));
      }, 1500);
      const wrappedResolve = value => { clearTimeout(timeout); resolve(value); };
      const wrappedReject = error => { clearTimeout(timeout); reject(error); };
      queue.push({ resolve: wrappedResolve, reject: wrappedReject });
      this.pending.set(command, queue);
    });
    await this.writer.write(frame);
    return reply;
  }

  rejectAll(error) {
    for (const queue of this.pending.values()) queue.forEach(item => item.reject(error));
    this.pending.clear();
  }
}

const remote = new URemoteSerial();
const $ = id => document.getElementById(id);
const configDefinition = [
  ["Firmware major", 0, true],
  ["Firmware minor", 1, true],
  ["Load calibration at startup", 2, false, 0, 1, "toggle"],
  ["Calibration duration (s)", 3, false, 1, 255],
  ["Shape threshold", 4, false, 0, 255],
  ["Emitter at startup", 5, false, 0, 1, "toggle"],
  ["CRC", 6, true]
];
let connected = false;
let pollTimer = null;
let pollBusy = false;
let toastTimer = null;
let lastStatusPollMs = 0;

function buildInterface() {
  $("sensorBars").innerHTML = Array.from({ length: 8 }, (_, i) => `
    <div class="sensor">
      <div class="bar-well"><div id="bar${i}" class="bar-fill"></div></div>
      <span id="sensor${i}" class="sensor-value">—</span>
      <span class="sensor-name">S${i + 1}</span>
    </div>`).join("");

  $("configFields").innerHTML = configDefinition.map(([name, index, readonly, min = 0, max = 255, type = "number"]) =>
    type === "toggle" ? `
      <div class="config-toggle">
        <span>${name}</span>
        <label class="switch" aria-label="${name}">
          <input id="config${index}" type="checkbox"><span></span>
        </label>
      </div>` : `
      <label>${name}
        <input id="config${index}" type="number" min="${min}" max="${max}" ${readonly ? "disabled" : ""}>
      </label>`).join("");

  $("calibrationLimits").innerHTML = Array.from({ length: 8 }, (_, i) => `
    <div class="limit-row"><span>S${i + 1}</span><span id="calMin${i}">—</span><span id="calMax${i}">—</span></div>`).join("");
  $("pixelIndex").innerHTML = Array.from({ length: 8 }, (_, i) =>
    `<option value="${i}">Pixel ${i + 1}</option>`).join("");
}

function setConnection(state) {
  connected = state;
  $("connectionDot").classList.toggle("online", state);
  $("connectionText").textContent = state ? "Connected" : "Disconnected";
  $("connectButton").textContent = state ? "Disconnect" : "Connect USB";
  if (!state) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function toast(message, error = false) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").className = `show${error ? " error" : ""}`;
  toastTimer = setTimeout(() => $("toast").className = "", 3000);
}

async function action(work, success) {
  try {
    await work();
    if (success) toast(success);
  } catch (error) {
    toast(error.message, true);
  }
}

function bytesFromReply(reply, command) {
  if (!(reply[0] instanceof Uint8Array)) throw new Error(`${command} returned invalid data`);
  return reply[0];
}

function renderReadings(packet) {
  for (let i = 0; i < 8; i++) {
    $("sensor" + i).textContent = packet[i];
    $("bar" + i).style.height = `${packet[i] * 100 / 255}%`;
  }
  const scaledPosition = Math.round(packet[8] * 256 / 255 - 128);
  $("position").value = scaledPosition;
  $("positionValue").textContent = scaledPosition;
  $("valueMin").textContent = packet[9];
  $("valueMax").textContent = packet[10];
  $("shape").textContent = packet[12] === 32 ? "None" : String.fromCharCode(packet[12]);
}

async function refreshConfig() {
  const bytes = bytesFromReply(await remote.call("get_config"), "get_config");
  bytes.forEach((value, index) => {
    const field = $("config" + index);
    if (!field) return;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else field.value = value;
  });
}

async function refreshCalibration() {
  const [minimums, maximums, calibrated] = await Promise.all([
    remote.call("get_cal_min"), remote.call("get_cal_max"), remote.call("is_calibrated")
  ]);
  bytesFromReply(minimums, "get_cal_min").forEach((value, i) => $("calMin" + i).textContent = value);
  bytesFromReply(maximums, "get_cal_max").forEach((value, i) => $("calMax" + i).textContent = value);
  $("calState").textContent = calibrated[0] ? "CALIBRATED" : "NOT LOADED";
}

function formatTrace(command, parameters, timestamp) {
  if (command === "-") return "No command recorded";
  return `${command}(${parameters}) · ${Number(timestamp) / 1000}s`;
}

function renderStatus(status) {
  const mode = Number(status[1]);
  const emitterOn = Boolean(status[3]);
  const ledMode = Number(status[4]);
  const modeNames = ["Raw", "Calibrated", "Digital", "Calibrating"];
  const ledModeNames = ["Off", "Normal", "Inverted", "Position"];

  $("statusEmitter").textContent = emitterOn ? "On" : "Off";
  $("statusEmitter").className = `status-value${emitterOn ? "" : " off"}`;
  $("statusMode").textContent = modeNames[mode] ?? `Mode ${mode}`;
  $("statusMode").className = `status-value${mode === 3 ? " busy" : ""}`;
  $("statusLedMode").textContent = ledModeNames[ledMode] ?? `Mode ${ledMode}`;
  $("statusLedMode").className = `status-value${ledMode === 0 ? " off" : ""}`;

  $("emitter").checked = emitterOn;
  $("ledMode").value = String(ledMode);
  $("rawMode").classList.toggle("active", mode !== 1);
  $("calMode").classList.toggle("active", mode === 1);
  $("sampleMode").textContent = modeNames[mode]?.toUpperCase() ?? `MODE ${mode}`;
  return mode;
}

async function refreshStatus() {
  const status = await remote.call("debug_status");
  renderStatus(status);
  lastStatusPollMs = performance.now();
  $("uptime").textContent = `${Math.floor(status[0] / 1000)} s`;
  $("overflows").textContent = status[5];
  const calibrated = Boolean(status[2]);
  const mode = Number(status[1]);
  $("calState").textContent = calibrated ? (mode === 3 ? "CALIBRATING" : "CALIBRATED") : "NOT LOADED";
}

async function refreshDebug() {
  await refreshStatus();
  const trace = await remote.call("last_commands");
  $("usartTrace").textContent = formatTrace(trace[0], trace[1], trace[2]);
  $("i2cTrace").textContent = formatTrace(trace[3], trace[4], trace[5]);
}

async function initializeDevice() {
  const uid = bytesFromReply(await remote.call("get_uid"), "get_uid");
  $("uid").textContent = [...uid].map(value => value.toString(16).padStart(2, "0")).join("").toUpperCase();
  await Promise.all([refreshConfig(), refreshCalibration(), refreshDebug()]);
  await pollReadings();
}

async function pollReadings() {
  if (!connected || pollBusy) return;
  pollBusy = true;
  try {
    renderReadings(bytesFromReply(await remote.call("all"), "all"));
    if (performance.now() - lastStatusPollMs >= 1000) await refreshStatus();
  } catch (error) {
    if (connected) toast(error.message, true);
  } finally {
    pollBusy = false;
  }
}

remote.disconnectHandler = async error => {
  if (!connected) return;
  setConnection(false);
  await remote.disconnect();
  toast(error.message, true);
};

$("connectButton").addEventListener("click", () => action(async () => {
  if (connected) {
    setConnection(false);
    await remote.disconnect();
    return;
  }
  await remote.connect();
  setConnection(true);
  try {
    await initializeDevice();
    pollTimer = setInterval(pollReadings, 250);
  } catch (error) {
    setConnection(false);
    await remote.disconnect();
    throw error;
  }
}, connected ? "Disconnected" : "USB connected"));

$("rawMode").addEventListener("click", () => action(async () => {
  await remote.call("set_mode_raw");
  await refreshDebug();
}, "Raw values selected"));
$("calMode").addEventListener("click", () => action(async () => {
  await remote.call("set_mode_cal");
  await refreshDebug();
}, "Calibrated values selected"));
$("emitter").addEventListener("change", event => action(async () => {
  await remote.call("set_emitter", event.target.checked ? 1 : 0);
  await refreshStatus();
}, `Emitter ${event.target.checked ? "on" : "off"}`));

$("loadConfig").addEventListener("click", () => action(refreshConfig, "Configuration refreshed"));
$("saveConfig").addEventListener("click", () => action(async () => {
  for (const [, index, readonly, min = 0, max = 255, type = "number"] of configDefinition) {
    if (readonly) continue;
    const input = $("config" + index);
    const value = type === "toggle" ? (input.checked ? 1 : 0) : Number(input.value);
    if (!Number.isInteger(value) || value < min || value > max) {
      throw new Error(`Configuration field ${index} is out of range`);
    }
    await remote.call("set_conf_value", index, value);
  }
  await remote.call("save_config");
  await refreshConfig();
}, "Configuration saved"));

$("startCalibration").addEventListener("click", () => action(async () => {
  await remote.call("calibrate", $("saveAfterCal").checked ? 1 : 0);
  await refreshDebug();
}, "Calibration started"));
$("loadCalibration").addEventListener("click", () => action(async () => {
  await remote.call("load_cal"); await refreshCalibration();
}, "Calibration loaded"));
$("saveCalibration").addEventListener("click", () => action(async () => {
  await remote.call("save_cal"); await refreshCalibration();
}, "Calibration saved"));
$("refreshCalibration").addEventListener("click", () => action(refreshCalibration));

$("setPixel").addEventListener("click", () => action(async () => {
  const color = $("pixelColor").value;
  await remote.call("leds", 0);
  await remote.call("neopixel", Number($("pixelIndex").value),
    parseInt(color.slice(1, 3), 16), parseInt(color.slice(3, 5), 16), parseInt(color.slice(5, 7), 16));
  await refreshStatus();
}, "Pixel updated"));
$("clearPixels").addEventListener("click", () => action(async () => {
  await remote.call("leds", 0);
  await refreshStatus();
}, "Pixels cleared"));
$("ledMode").addEventListener("change", event => action(async () => {
  await remote.call("leds", Number(event.target.value));
  await refreshStatus();
}, `LED mode: ${event.target.selectedOptions[0].text}`));
$("refreshDebug").addEventListener("click", () => action(refreshDebug));

function applyTheme(theme) {
  const selectedTheme = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = selectedTheme;
  const dark = selectedTheme === "dark";
  $("themeToggle").textContent = dark ? "Light mode" : "Dark mode";
  $("themeToggle").setAttribute("aria-pressed", String(dark));
  document.querySelector('meta[name="theme-color"]').content = dark ? "#07110f" : "#f8f9fa";
  try {
    localStorage.setItem("line-sensor-theme", selectedTheme);
  } catch (_) {
    // Theme still works when local storage is unavailable.
  }
}

$("themeToggle").addEventListener("click", () => {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
});

buildInterface();
setConnection(false);
applyTheme(document.documentElement.dataset.theme);
