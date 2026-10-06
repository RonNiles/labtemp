# labtemp: lab ambient and chassis temperature

A Tasmota board with two DS18B20 probes publishes over MQTT to this host. The readings are stored in InfluxDB 2 and
graphed in Grafana. Everything runs in one rootless podman container, `labtemp`, under supervisord:

| program    | what                                                        | port                     |
|------------|-------------------------------------------------------------|--------------------------|
| mosquitto  | MQTT broker, password login + per-user access rules         | 1883 (all interfaces)    |
| subscriber | `tele/tasmota_F0A93B/SENSOR` -> InfluxDB (`subscriber.py`)  | -                        |
| influxd    | InfluxDB 2, org `lab`, bucket `labtemp`, kept forever       | 8086 (127.0.0.1 only)    |
| grafana    | dashboard "Lab Temperature" (home page)                     | 3001 (all interfaces)    |

The Memory Machine X Grafana on this host is a separate instance (port 8092, behind Caddy on 8080). This container
doesn't touch it.

## View
`http://<lab-amd0>:3001/`. Anonymous access is read-only. To edit, log in as `admin` with the password in
`data/secrets/grafana-admin`.

## Point the sensor here
In the Tasmota console: `Backlog MqttHost <lab-amd0 IP>; MqttPort 1883; MqttUser tasmota; MqttPassword <data/secrets/mqtt-tasmota>; TelePeriod 60`
(TelePeriod defaults to 300 s). The sensor's web server is off (`Webserver 0`), so change its settings over MQTT, see below. lab-amd0's Wi-Fi address comes from DHCP and changes. Give it a reservation
(MAC 74:19:f8:17:5e:3a), or the sensor will lose the broker.

## Broker logins
Anonymous access is off. Passwords are in `data/secrets/mqtt-<user>`, and `entrypoint.sh` hashes them into the broker's
password file on every start. To change one, edit the file and run `systemctl --user restart labtemp`.
Access rules are in `mosquitto.acl`:

| user       | may                                                                      |
|------------|--------------------------------------------------------------------------|
| tasmota    | publish `tele/` and `stat/tasmota_F0A93B/#`; receive its own commands    |
| subscriber | read `tele/tasmota_F0A93B/SENSOR`                                        |
| admin      | everything, and it is the only login that can send the sensor commands   |

Send the sensor a command (example: report full status):
```
podman exec labtemp sh -c 'mosquitto_pub -u admin -P "$(cat /data/secrets/mqtt-admin)" -t cmnd/tasmota_F0A93B/Status -m 0'
```
Sensor hardening (2026-10-06): `Webserver 0`, `WifiConfig 4` (no fallback setup hotspot), `Emulation 0`,
`SetOption55 0` (no mDNS), `SetOption1 1` (no button multi-press actions). Its web password, for when the web
server is turned back on, is in `data/secrets/tasmota-web`. Querying `WebPassword` returns it in plain text.

If you change the `tasmota` password, send the sensor `MqttPassword <new>` **before** restarting the broker, or it
will be locked out, and then only a serial cable can fix it.

## Data
Measurement `temperature`, field `value`, tags `probe` (DS18B20-1...), `id` (probe ROM id), `unit` (F). The timestamp
is when the reading was received; Tasmota's `Time` has no timezone. A new probe is picked up automatically.

## Name the probes
The dashboard labels series by probe id. When you know which probe is ambient and which is chassis, edit the `names`
dict at the top of the two queries in `grafana/dashboards/lab-temp.json`. Grafana reloads it within 30 s. Stored
data is keyed by id, so it never needs rewriting.

## Operate
```
systemctl --user status labtemp                    # quadlet unit; starts at boot (linger)
podman logs -f labtemp                             # all four programs log here
podman exec labtemp supervisorctl status
podman exec labtemp sh -c 'mosquitto_sub -u admin -P "$(cat /data/secrets/mqtt-admin)" -t "tele/#" -v'   # watch raw telemetry
podman exec labtemp influx query 'from(bucket:"labtemp") |> range(start:-1h)'
```
Rebuild after changing `subscriber.py`, the configs or the Containerfile:
`podman build -t localhost/labtemp:latest ~/labtemp && systemctl --user restart labtemp`.
`grafana/` is bind-mounted, so dashboard edits need no rebuild.

## Back up
Everything that persists is in `data/` (InfluxDB, Grafana, secrets; the broker keeps no state). Stop the unit and copy it.
`data/` is gitignored.
