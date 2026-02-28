"""
evcc-crowdscience-bridge
Forwards local evcc MQTT topics to the HTW Berlin Crowdscience broker via WSS.
Configuration via environment variables (see .env.example).
"""

import os
import ssl
import time
import paho.mqtt.client as mqtt

LOCAL_HOST     = os.environ.get("LOCAL_HOST", "mosquitto")
LOCAL_PORT     = int(os.environ.get("LOCAL_PORT", 1883))
LOCAL_USER     = os.environ.get("LOCAL_USER", "mqtt")
LOCAL_PASSWORD = os.environ.get("LOCAL_PASSWORD", "")

REMOTE_HOST    = os.environ.get("REMOTE_HOST", "mqtt.evcc-crowdscience.de")
REMOTE_PORT    = int(os.environ.get("REMOTE_PORT", 443))
DEVICE_ID      = os.environ["DEVICE_ID"]
LOCAL_TOPIC    = os.environ.get("LOCAL_TOPIC", "evcc")

remote_client  = None


def on_local_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to local broker", flush=True)
        client.subscribe(f"{LOCAL_TOPIC}/#", qos=1)
    else:
        print(f"Local connect failed: rc={rc}", flush=True)


def on_local_message(client, userdata, msg):
    suffix = msg.topic[len(LOCAL_TOPIC) + 1:]
    remote_topic = f"evcc/{DEVICE_ID}/{suffix}"
    remote_client.publish(remote_topic, msg.payload, qos=1)


def create_remote_client():
    client = mqtt.Client(transport="websockets")
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    client.on_connect = lambda c, u, f, rc: print(
        "Connected to remote broker" if rc == 0 else f"Remote connect failed: rc={rc}",
        flush=True,
    )
    return client


remote_client = create_remote_client()
remote_client.connect(REMOTE_HOST, REMOTE_PORT, keepalive=60)
remote_client.loop_start()

local_client = mqtt.Client()
local_client.username_pw_set(LOCAL_USER, LOCAL_PASSWORD)
local_client.on_connect = on_local_connect
local_client.on_message = on_local_message

while True:
    try:
        local_client.connect(LOCAL_HOST, LOCAL_PORT, keepalive=60)
        local_client.loop_forever()
    except Exception as e:
        print(f"Connection error: {e} – retrying in 10s", flush=True)
        time.sleep(10)
