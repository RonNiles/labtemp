#!/bin/bash
# First run: create the InfluxDB org/bucket and the secrets Grafana and the subscriber read.
# Later runs: straight to supervisord.
set -euo pipefail

mkdir -p /data/influxdb /data/grafana /data/secrets
chmod 700 /data/secrets

gen() { python3 -c 'import secrets; print(secrets.token_urlsafe(32))'; }

[ -s /data/secrets/grafana-admin ] || gen > /data/secrets/grafana-admin

if [ ! -s "$INFLUXD_BOLT_PATH" ]; then
    echo "entrypoint: first run, initializing InfluxDB"
    gen > /data/secrets/influx-token
    gen > /data/secrets/influx-admin
    influxd >/data/influxdb/init.log 2>&1 &
    pid=$!
    for _ in $(seq 60); do
        curl -fs http://localhost:8086/health >/dev/null && break
        sleep 1
    done
    influx setup --force \
        --username admin --password "$(cat /data/secrets/influx-admin)" \
        --token "$(cat /data/secrets/influx-token)" \
        --org lab --bucket labtemp --retention 0
    kill "$pid"
    wait "$pid" || true
fi

exec /usr/bin/supervisord -c /etc/labtemp/supervisord.conf
