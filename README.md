# evcc-crowdscience-bridge

Forwards local [evcc](https://evcc.io/) MQTT topics to the [HTW Berlin Crowdscience](https://evcc-crowdscience.de/) broker via WebSocket Secure (WSS).

evcc supports only a single MQTT broker. If you already use a local Mosquitto broker for evcc (e.g. for home automation), you cannot point evcc directly to the Crowdscience broker at the same time. This bridge solves that by forwarding messages from your local broker to the Crowdscience broker.

## How it works

```
evcc → local Mosquitto (MQTT) → bridge → mqtt.evcc-crowdscience.de (WSS/443)
```

The bridge subscribes to `<LOCAL_TOPIC>/#` on your local broker and republishes all messages to `evcc/<DEVICE_ID>/<suffix>` on the Crowdscience broker.

## Prerequisites

- A running local MQTT broker (e.g. Mosquitto)
- Your Crowdscience Device ID from [evcc-crowdscience.de](https://evcc-crowdscience.de/)

## Setup

### Docker

```bash
cp .env.example .env
$EDITOR .env
docker compose up -d
docker compose logs -f
```

> **Note:** If your Mosquitto runs in a separate Docker Compose stack, the default `LOCAL_HOST=mosquitto` won't resolve (no shared Docker network). Set `LOCAL_HOST` to the host's IP or hostname instead.

If you want to run Mosquitto and the bridge together in one stack, see [`docker-compose.example.yml`](docker-compose.example.yml) for a complete example.

### systemd (without Docker)

Install the dependency:

```bash
pip install paho-mqtt==1.6.1
```

Create `/etc/evcc-crowdscience-bridge.env`:

```ini
DEVICE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
LOCAL_HOST=localhost
LOCAL_USER=mqtt
LOCAL_PASSWORD=secret
```

Copy the included service file and the bridge script:

```bash
sudo mkdir -p /opt/evcc-crowdscience-bridge
sudo cp bridge.py /opt/evcc-crowdscience-bridge/bridge.py
sudo cp evcc-crowdscience-bridge.service /etc/systemd/system/
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now evcc-crowdscience-bridge
sudo journalctl -fu evcc-crowdscience-bridge
```

## Configuration

| Variable         | Required | Default                        | Description                          |
|-----------------|----------|--------------------------------|--------------------------------------|
| `LOCAL_HOST`     | no       | `mosquitto`                    | Hostname/IP of your local broker     |
| `LOCAL_PORT`     | no       | `1883`                         | Port of your local broker            |
| `LOCAL_USER`     | no       | `mqtt`                        | MQTT username                        |
| `LOCAL_PASSWORD` | no       | _(empty)_                      | MQTT password                        |
| `DEVICE_ID`      | yes      | –                              | Your Crowdscience Device ID          |
| `LOCAL_TOPIC`    | no       | `evcc`                         | Local MQTT topic prefix to subscribe |
| `REMOTE_HOST`    | no       | `mqtt.evcc-crowdscience.de`    | Crowdscience broker hostname         |
| `REMOTE_PORT`    | no       | `443`                          | Crowdscience broker port (WSS)       |
| `STATS_INTERVAL`      | no  | `300`                          | Interval in seconds for throughput stats logged to stdout |
| `FILTER_ENABLED`      | no  | `true`                         | Set to `false` or `0` to disable topic filtering (useful for debugging) |
| `LOCAL_FILTER_PATH`   | no  | `filter-local.json`            | Path to a local blacklist file (see [Filtering](#filtering)) |
| `LOCAL_WHITELIST_PATH`| no  | `whitelist-local.json`         | Path to a local whitelist file (see [Filtering](#filtering)) |

## Stats

The bridge periodically logs throughput to stdout:

```
Stats: 142 messages in last 5 min (total: 1847)
```

Adjust the interval via `STATS_INTERVAL` (default: 300 s). Set it to `0` to disable stats.

## Filtering

On startup the bridge fetches the [filter configuration](https://github.com/htw-solarspeichersysteme/evcc-crowdscience/blob/main/apps/transporter/src/lib/filtering.ts) from the upstream Crowdscience repository. If the file cannot be fetched the bridge starts **without filtering** and logs a warning.

Filtering reduces outbound traffic: evcc publishes many topics that are irrelevant for research purposes (config, credentials, tariffs, forecast, …), which can make up the majority of all messages. The remote broker would discard them anyway — dropping them locally saves bandwidth.

### Blacklist mode (default)

Drops topics matching the upstream filter rules:

- Topics whose suffix starts with one of the **config prefixes** (e.g. credentials, certificates)
- Topics whose suffix contains one of the **invalid substrings** (e.g. `forecast`, `title`)

A **local blacklist** (`filter-local.json`) can extend the upstream rules with additional entries. This is useful for topics added in pending PRs that are not yet merged into the upstream filter:

```json
{
  "configPrefixes": ["site/eebus/", "site/ocpp/"],
  "invalidSubstrings": []
}
```

### Whitelist mode

If `whitelist-local.json` is present, the bridge switches to whitelist mode: only topics matching one of the listed patterns are forwarded, and the blacklist is inactive. The `+` wildcard matches exactly one topic level.

```json
{
  "allowedPatterns": [
    "updated",
    "site/+",
    "site/pv/+/+",
    "site/battery/+",
    "loadpoints/+/+"
  ]
}
```

A ready-to-use `whitelist-local.json` covering all measurements queried by the Crowdscience web app is included in this repository.

Startup log shows the active mode:

```
Filter loaded: 9 config prefixes, 6 invalid substrings
Local filter loaded: +5 config prefixes, +0 invalid substrings (filter-local.json)
Whitelist: not configured (whitelist-local.json not found) – using blacklist
```

```
Whitelist loaded: 20 patterns (whitelist-local.json) – blacklist inactive
```

## Legal

**Data privacy:** This bridge transmits energy and charging data from your local system to the HTW Berlin Crowdscience broker. Depending on your jurisdiction, this data may constitute personal data under applicable privacy law (e.g. GDPR). You are solely responsible for ensuring that you are entitled to share this data and that doing so complies with applicable law.

**Disclaimer:** This software is provided "as is", without warranty of any kind. The authors are not liable for any damages or data loss arising from its use.

## Notes

- The Crowdscience broker accepts data **without authentication** – only reading requires authorization.
- Data is transmitted encrypted (TLS).
- Mosquitto does not support WebSocket bridges natively, hence this separate bridge container.
- the DEVICE_ID is without prefix (no 'evcc/')
