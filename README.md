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

## Notes

- The Crowdscience broker accepts data **without authentication** – only reading requires authorization.
- Data is transmitted encrypted (TLS).
- Mosquitto does not support WebSocket bridges natively, hence this separate bridge container.
