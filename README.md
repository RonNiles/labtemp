# labtemp: lab ambient and chassis temperature

A Tasmota board with two DS18B20 probes publishes over MQTT to this host. The readings are stored in InfluxDB 2 and
graphed in Grafana. Everything runs in one rootless podman container, `labtemp`, under supervisord:

| program    | what                                                        | port                     |
|------------|-------------------------------------------------------------|--------------------------|
| mosquitto  | MQTT broker, **unauthenticated**                            | 1883 (all interfaces)    |
| subscriber | `tele/tasmota_F0A93B/SENSOR` -> InfluxDB (`subscriber.py`)  | -                        |
| influxd    | InfluxDB 2, org `lab`, bucket `labtemp`, kept forever       | 8086 (127.0.0.1 only)    |
| grafana    | dashboard "Lab Temperature" (home page)                     | 3001 (all interfaces)    |

The Memory Machine X Grafana on this host is a separate instance (port 8092, behind Caddy on 8080). This container
doesn't touch it.

## View
`http://<lab-amd0>:3001/`. Anonymous access is read-only. To edit, log in as `admin` with the password in
`data/secrets/grafana-admin`.

## Point the sensor here
In the Tasmota console: `Backlog MqttHost <lab-amd0 IP>; MqttPort 1883; TelePeriod 60`
(TelePeriod defaults to 300 s). lab-amd0's Wi-Fi address comes from DHCP and changes. Give it a reservation
(MAC 74:19:f8:17:5e:3a), or the sensor will lose the broker.

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
podman exec labtemp mosquitto_sub -t 'tele/#' -v   # watch raw telemetry
podman exec labtemp influx query 'from(bucket:"labtemp") |> range(start:-1h)'
```
Rebuild after changing `subscriber.py`, the configs or the Containerfile:
`podman build -t localhost/labtemp:latest ~/labtemp && systemctl --user restart labtemp`.
`grafana/` is bind-mounted, so dashboard edits need no rebuild.

## Back up
Everything that persists is in `data/` (InfluxDB, Grafana, secrets; the broker keeps no state). Stop the unit and copy it.
`data/` is gitignored.
