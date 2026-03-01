# Narwal Flow Robot Vacuum — Home Assistant Integration

A fully **local, cloud-independent** [Home Assistant](https://www.home-assistant.io/) custom integration for Narwal robot vacuums. Communicates directly with your vacuum over your local network via WebSocket — no cloud account or internet connection required.

> **Status: v0.3.0 — Early Release** — Core vacuum control, sensors, and map display are working for the Narwal Flow (AX12). Other model support is being explored. Use at your own risk.

## Device Compatibility

This integration uses a **local WebSocket connection on port 9002**. Only models that expose this port can be supported — models that communicate exclusively through Narwal's cloud servers cannot be controlled locally.

| Model | Internal Code | Local Port 9002 | Status | Notes |
|-------|---------------|:---------------:|--------|-------|
| **Narwal Flow** | AX12 | Yes | **Working** | Core vacuum control and sensors functional; map in progress |
| **Freo Z10 Ultra** | — | Yes | **Partial** | Connects and broadcasts; state mapping and wake reliability under investigation |
| **Freo X Ultra** | AX18/AX19 | Varies | **Under Investigation** | Some units have port 9002, others use ZeroMQ on port 6789 |
| **Freo X Plus** | — | No | **Not Supported** | Cloud-only (MQTT via Narwal servers) — no local API available |

### What "Not Supported" means

Models marked **Not Supported** communicate exclusively through Narwal's cloud servers. There is no local API to connect to, so this integration cannot control them. This is a hardware/firmware limitation, not something that can be fixed in software.

### Other models

If your Narwal model is not listed above, it *may* work if it exposes a local WebSocket on port 9002. To check:

```bash
nmap -p 9002 <your-vacuum-ip>
```

If port 9002 is open, please [open an issue](https://github.com/sjmotew/NarwalIntegration/issues/new/choose) with your model name and nmap results — we'd love to test it.

## Features

### Vacuum Control
- **Start / Stop / Pause / Resume** cleaning
- **Return to dock**
- **Locate** — robot announces "Robot is here"
- **Fan speed control** — Quiet, Normal, Strong, Max (set-only; robot does not broadcast current level)

### Sensors
- **Battery level** — real-time percentage from robot broadcasts
- **Cleaning area** — square meters cleaned in current session (only populated during active cleaning)
- **Cleaning time** — current session duration (only populated during active cleaning)
- **Firmware version** — diagnostic sensor
- **Docked status** — binary sensor (on dock / off dock)

### Map (In Progress)
- **Floor plan image** — basic color-coded room map rendered from robot's stored map data
- Map rendering is functional but still being refined — dock position, room labels, and map freshness are not yet reliable
- The robot may return an outdated map until a new clean is run

### Connectivity
- **Real-time updates** — WebSocket push (~1.5s when robot is awake)
- **Auto-reconnect** with exponential backoff
- **Wake system** — sends wake commands to rouse a sleeping robot (best-effort; not always reliable, especially after long idle periods)
- **Keepalive heartbeat** — helps prevent robot from going back to sleep during a session
- **Polling fallback** — 60-second poll if push updates stop

## Installation

### HACS (Recommended)

1. Open Home Assistant and go to **HACS** in the sidebar.
2. Click the **three-dot menu** (top right) and select **Custom repositories**.
3. Add the repository URL:
   ```
   https://github.com/sjmotew/NarwalIntegration
   ```
4. Set the category to **Integration** and click **Add**.
5. Find **Narwal Flow Robot Vacuum** in the HACS store and click **Download**.
6. **Restart Home Assistant**.

### Manual Installation

1. Download or clone this repository.
2. Copy the `custom_components/narwal/` folder into your Home Assistant `config/custom_components/` directory.
3. **Restart Home Assistant**.

### Setup

1. Go to **Settings > Devices & Services > Add Integration**.
2. Search for **Narwal Flow Robot Vacuum**.
3. Enter your vacuum's **IP address** (find it in your router's DHCP table or the Narwal app).
4. The integration will connect, discover the device, and create all entities automatically.

> **Tip:** Assign a static IP to your vacuum in your router settings so the address doesn't change.

## Requirements

- Narwal robot vacuum on the same local network as Home Assistant
- The vacuum must be reachable on **port 9002** (no firewall blocking)
- Home Assistant **2025.1.0** or later
- Python **3.12** or later

## How It Works

This integration communicates with your Narwal vacuum over a local WebSocket connection on port 9002. The vacuum uses a binary protobuf-like protocol — the integration reverse-engineered this protocol to provide local control without any cloud dependency.

When the robot is awake, it broadcasts status updates every ~1.5 seconds. The integration listens to these broadcasts and keeps HA entities up to date in real time. Commands (start, stop, pause, etc.) are sent over the same WebSocket connection.

### Robot Sleep Behavior

The Narwal vacuum enters a low-power sleep mode when idle. During sleep, the WebSocket port stays open but the robot may not respond to commands or send broadcasts. The integration sends wake commands derived from the official app's protocol, but **wake reliability varies** — the robot may take 30+ seconds to respond, or may not respond at all until you open the Narwal app once or start a clean from the app.

A keepalive heartbeat runs every 15 seconds to help prevent the robot from going back to sleep once awake, but this is not guaranteed — the robot can still drop into deep sleep during long idle periods.

## Known Limitations

### Working
- Vacuum controls (start, stop, pause, resume, return to dock, locate)
- Battery level sensor
- Cleaning area and cleaning time sensors (populated during active cleaning only)
- Firmware version sensor
- Docked status detection

### In Progress
- **Map rendering** — A basic floor plan image is generated from the robot's stored map data. However, dock position overlay is not consistently accurate, the robot may return a stale/outdated map, and room labels need work. This feature is actively being improved.
- **Fan speed** — You can set fan speed, but the robot does not broadcast its current level. The integration tracks the last value you set; changes made via the Narwal app won't be reflected.
- **Live map updates** — The robot sends position broadcasts during cleaning, but real-time map overlay needs more testing.

### Not Yet Implemented
- **Room-specific cleaning** — The protocol supports it, but the room selection payload format needs further decoding.
- **Cleaning history / statistics** — Not implemented.
- **Camera / video streaming** — Images are AES-encrypted (key on phone app only). Video uses Agora (cloud-only). Not feasible locally.

### Known Issues
- **Wake from deep sleep is unreliable** — The robot may not respond to wake commands after long idle periods. Opening the Narwal app or starting a clean from the app can help "prime" the robot. Once awake, the integration keeps it responsive, but it can still drop back to sleep.
- **Single connection** — The vacuum only handles one WebSocket connection reliably. Close the Narwal app before using the HA integration to avoid interference.
- **Map may be stale** — The robot can return an old map from a previous layout. Running a new clean cycle typically refreshes it.
- **Local network only** — Your HA instance must be on the same network as the vacuum.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Cannot connect" during setup | Verify the vacuum's IP address and that port 9002 is not blocked. The robot must be powered on. |
| Entities show "Unavailable" | The robot may be asleep. Open the Narwal app briefly or start a clean to wake it, then the integration will take over. |
| Map not showing or outdated | The map requires a successful `get_map` response. If the robot was asleep, the map appears after it wakes. The robot may return a stale map — running a new clean typically refreshes it. |
| Commands not responding | Ensure the Narwal app is closed — two simultaneous WebSocket connections cause issues. |
| Fan speed shows unknown | Set fan speed once from HA; it will track from that point. The robot doesn't broadcast this value. |
| Docked status wrong | The integration uses multiple signals to detect dock status. If you see issues, please [report a bug](https://github.com/sjmotew/NarwalIntegration/issues/new/choose) with debug logs. |

## Reporting Issues

Please use the [issue templates](https://github.com/sjmotew/NarwalIntegration/issues/new/choose) when reporting bugs. The templates ask for your HA version, Narwal model, integration version, and debug logs — this information is essential for diagnosing problems quickly.

## Disclaimer

This is an **unofficial**, community-developed integration. It is not affiliated with, endorsed by, or supported by Narwal in any way. The local WebSocket protocol was reverse-engineered from publicly observable network traffic and the Narwal mobile application.

- **Use at your own risk.** This integration sends commands to your vacuum over the local network. While every effort has been made to ensure commands are safe and correct, there is no warranty.
- **No cloud dependency.** This integration does not connect to Narwal's cloud servers, does not transmit any data externally, and does not require an internet connection.
- **Firmware updates** from Narwal may change the local protocol at any time, potentially breaking this integration.

## Contributing

Contributions and testing are welcome! Please open an issue or pull request on [GitHub](https://github.com/sjmotew/NarwalIntegration).

If you have a Narwal model other than the Flow (AX12), testing reports are especially valuable — but please note that our current priority is stabilizing the Flow integration before expanding to other models.

## License

MIT
