# Lab temperature telemetry: mosquitto + InfluxDB 2 + Grafana + MQTT subscriber, one container.
FROM docker.io/library/ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
 && install -d -m 0755 /etc/apt/keyrings \
 && curl -fsSL https://repos.influxdata.com/influxdata-archive.key | gpg --dearmor -o /etc/apt/keyrings/influxdata.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/influxdata.gpg] https://repos.influxdata.com/debian stable main" \
      > /etc/apt/sources.list.d/influxdata.list \
 && curl -fsSL https://apt.grafana.com/gpg.key | gpg --dearmor -o /etc/apt/keyrings/grafana.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" \
      > /etc/apt/sources.list.d/grafana.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      mosquitto mosquitto-clients influxdb2 influxdb2-cli grafana \
      supervisor python3 python3-paho-mqtt \
 && rm -rf /var/lib/apt/lists/*

# influxd and the influx CLI keep everything under /data so it survives container recreation.
ENV INFLUXD_BOLT_PATH=/data/influxdb/influxd.bolt \
    INFLUXD_ENGINE_PATH=/data/influxdb/engine \
    INFLUXD_HTTP_BIND_ADDRESS=:8086 \
    INFLUXD_REPORTING_DISABLED=true \
    INFLUX_CONFIGS_PATH=/data/influxdb/cli-configs \
    INFLUX_HOST=http://localhost:8086

COPY supervisord.conf /etc/labtemp/
COPY mosquitto.conf /etc/mosquitto/labtemp.conf
COPY subscriber.py entrypoint.sh /usr/local/bin/
# grafana/ is also bind-mounted over this at run time so dashboard edits need no rebuild.
COPY grafana /etc/labtemp/grafana

EXPOSE 1883 3001 8086
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
