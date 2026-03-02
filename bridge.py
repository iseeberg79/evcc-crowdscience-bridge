"""
evcc-crowdscience-bridge
Forwards local evcc MQTT topics to the HTW Berlin Crowdscience broker via WSS.
Configuration via environment variables (see .env.example).
"""

import json
import os
import re
import ssl
import time
import threading
import urllib.request
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
msg_count      = 0

STATS_INTERVAL      = int(os.environ.get("STATS_INTERVAL", 300))
FILTER_ENABLED      = os.environ.get("FILTER_ENABLED", "true").lower() not in ("false", "0")
LOCAL_FILTER_PATH   = os.environ.get("LOCAL_FILTER_PATH", "filter-local.json")
LOCAL_WHITELIST_PATH = os.environ.get("LOCAL_WHITELIST_PATH", "whitelist-local.json")

FILTERING_TS_URL = (
    "https://raw.githubusercontent.com/htw-solarspeichersysteme/"
    "evcc-crowdscience/main/apps/transporter/src/lib/filtering.ts"
)


def load_filter_from_ts():
    try:
        with urllib.request.urlopen(FILTERING_TS_URL, timeout=5) as r:
            src = r.read().decode()
        def parse_array(name):
            m = re.search(rf'{name}\s*=\s*\[(.*?)\]', src, re.DOTALL)
            return re.findall(r'"([^"]+)"', m.group(1)) if m else []
        config_prefixes   = parse_array("configPrefixes")
        invalid_substrings = parse_array("invalidSubstrings")
        if not config_prefixes and not invalid_substrings:
            raise ValueError("parsed empty filter config")
        return config_prefixes, invalid_substrings
    except Exception as e:
        print(f"Warning: could not load filter config ({e}) – forwarding unfiltered", flush=True)
        return None, None


def make_filter(config_prefixes, invalid_substrings):
    if config_prefixes is None:
        return lambda suffix: False
    def filter_topic(suffix):
        if any(suffix.startswith(p) for p in config_prefixes):
            return True
        if any(kw in suffix.lower() for kw in invalid_substrings):
            return True
        return False
    return filter_topic


def mqtt_pattern_match(pattern, topic):
    parts_p, parts_t = pattern.split("/"), topic.split("/")
    if len(parts_p) != len(parts_t):
        return False
    return all(p == "+" or p == t for p, t in zip(parts_p, parts_t))


def load_local_whitelist():
    try:
        with open(LOCAL_WHITELIST_PATH) as f:
            patterns = json.load(f).get("allowedPatterns", [])
        if not patterns:
            return None
        print(f"Whitelist loaded: {len(patterns)} patterns ({LOCAL_WHITELIST_PATH}) – blacklist inactive", flush=True)
        return patterns
    except FileNotFoundError:
        print(f"Whitelist: not configured ({LOCAL_WHITELIST_PATH} not found) – using blacklist", flush=True)
        return None
    except Exception as e:
        print(f"Warning: could not load whitelist ({e}) – using blacklist", flush=True)
        return None


def load_local_filter():
    try:
        with open(LOCAL_FILTER_PATH) as f:
            data = json.load(f)
        prefixes = data.get("configPrefixes", [])
        substrings = data.get("invalidSubstrings", [])
        print(f"Local filter loaded: +{len(prefixes)} config prefixes, +{len(substrings)} invalid substrings ({LOCAL_FILTER_PATH})", flush=True)
        return prefixes, substrings
    except FileNotFoundError:
        print(f"Local filter: not configured ({LOCAL_FILTER_PATH} not found)", flush=True)
        return [], []
    except Exception as e:
        print(f"Warning: could not load local filter ({e})", flush=True)
        return [], []


if FILTER_ENABLED:
    config_prefixes, invalid_substrings = load_filter_from_ts()
    if config_prefixes is not None:
        print(f"Filter loaded: {len(config_prefixes)} config prefixes, {len(invalid_substrings)} invalid substrings", flush=True)
    local_config, local_invalid = load_local_filter()
    if local_config or local_invalid:
        config_prefixes = (config_prefixes or []) + local_config
        invalid_substrings = (invalid_substrings or []) + local_invalid
else:
    print("Filtering disabled via FILTER_ENABLED=false", flush=True)
    config_prefixes, invalid_substrings = None, None
filter_topic = make_filter(config_prefixes, invalid_substrings)
whitelist = load_local_whitelist()

print(f"Device ID: {DEVICE_ID}", flush=True)
print(f"Publishing to: evcc/{DEVICE_ID}/<suffix>", flush=True)


def stats_loop():
    last = 0
    while True:
        time.sleep(STATS_INTERVAL)
        total = msg_count
        print(f"Stats: {total - last} messages in last {STATS_INTERVAL // 60} min (total: {total})", flush=True)
        last = total



def on_local_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to local broker", flush=True)
        client.subscribe(f"{LOCAL_TOPIC}/#", qos=1)
    else:
        print(f"Local connect failed: rc={rc}", flush=True)


def on_local_message(client, userdata, msg):
    global msg_count
    suffix = msg.topic[len(LOCAL_TOPIC) + 1:]
    if whitelist is not None:
        if not any(mqtt_pattern_match(p, suffix) for p in whitelist):
            return
    elif filter_topic(suffix):
        return
    remote_topic = f"evcc/{DEVICE_ID}/{suffix}"
    remote_client.publish(remote_topic, msg.payload, qos=1)
    msg_count += 1


def create_remote_client():
    client = mqtt.Client(transport="websockets")
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    client.on_connect = lambda c, u, f, rc: print(
        "Connected to remote broker" if rc == 0 else f"Remote connect failed: rc={rc}",
        flush=True,
    )
    client.on_disconnect = lambda c, u, rc: print(
        f"Disconnected from remote broker: rc={rc}",
        flush=True,
    )
    return client


if STATS_INTERVAL > 0:
    threading.Thread(target=stats_loop, daemon=True).start()

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
