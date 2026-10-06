#!/usr/bin/env python3
"""Subscribe to the Tasmota DS18B20 telemetry and write each probe reading to InfluxDB 2.

Every top-level key whose value is an object with a numeric "Temperature" becomes one point:
    temperature,probe=DS18B20-1,id=000000C43585,unit=F value=78.6 <receive time ns>
Tasmota's "Time" field carries no timezone, so the receive time is used instead.
"""
import json
import logging
import os
import time
import urllib.error
import urllib.request

import paho.mqtt.client as mqtt

TOPIC = os.environ.get("LABTEMP_TOPIC", "tele/tasmota_F0A93B/SENSOR")
MQTT_HOST = "localhost"
MQTT_PORT = 1883
INFLUX_URL = os.environ.get("INFLUX_HOST", "http://localhost:8086")
WRITE_URL = f"{INFLUX_URL}/api/v2/write?org=lab&bucket=labtemp&precision=ns"
TOKEN_FILE = "/data/secrets/influx-token"
MQTT_USER = "subscriber"
MQTT_PASSWORD_FILE = "/data/secrets/mqtt-subscriber"

log = logging.getLogger("subscriber")


def tag(value):
    """Escape a tag value for InfluxDB line protocol."""
    return str(value).replace("\\", "\\\\").replace(",", r"\,").replace(" ", r"\ ").replace("=", r"\=")


def to_lines(payload, ts_ns):
    unit = payload.get("TempUnit")
    lines = []
    for key, val in payload.items():
        if not isinstance(val, dict):
            continue
        temp = val.get("Temperature")
        if isinstance(temp, bool) or not isinstance(temp, (int, float)):
            continue
        tags = f"probe={tag(key)}"
        if val.get("Id"):
            tags += f",id={tag(val['Id'])}"
        if unit:
            tags += f",unit={tag(unit)}"
        lines.append(f"temperature,{tags} value={float(temp)} {ts_ns}")
    return lines


def write(lines, token):
    req = urllib.request.Request(
        WRITE_URL,
        data="\n".join(lines).encode(),
        headers={"Authorization": f"Token {token}", "Content-Type": "text/plain; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10):
        pass


def on_connect(client, userdata, flags, rc, properties=None):
    log.info("connected to broker (rc=%s), subscribing to %s", rc, TOPIC)
    client.subscribe(TOPIC, qos=0)


def on_message(client, userdata, msg):
    ts_ns = time.time_ns()
    try:
        payload = json.loads(msg.payload)
    except ValueError as e:
        log.warning("bad JSON on %s: %s: %r", msg.topic, e, msg.payload[:200])
        return
    if not isinstance(payload, dict):
        log.warning("unexpected payload on %s: %r", msg.topic, msg.payload[:200])
        return
    lines = to_lines(payload, ts_ns)
    if not lines:
        log.warning("no temperatures in message: %r", msg.payload[:200])
        return
    try:
        write(lines, userdata["token"])
    except (urllib.error.URLError, OSError) as e:
        body = e.read()[:200] if isinstance(e, urllib.error.HTTPError) else b""
        log.error("InfluxDB write failed, %d point(s) dropped: %s %r", len(lines), e, body)
        return
    log.info("wrote %s", "; ".join(line.split(" ", 2)[0] + " " + line.split(" ", 2)[1] for line in lines))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s subscriber %(levelname)s %(message)s")
    while not os.path.exists(TOKEN_FILE):
        log.info("waiting for %s", TOKEN_FILE)
        time.sleep(2)
    with open(TOKEN_FILE) as f:
        token = f.read().strip()

    kwargs = {"client_id": "labtemp-subscriber", "userdata": {"token": token}}
    if hasattr(mqtt, "CallbackAPIVersion"):  # paho-mqtt 2.x
        kwargs["callback_api_version"] = mqtt.CallbackAPIVersion.VERSION1
    client = mqtt.Client(**kwargs)
    with open(MQTT_PASSWORD_FILE) as f:
        client.username_pw_set(MQTT_USER, f.read().strip())
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
