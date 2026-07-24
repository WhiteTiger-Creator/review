#!/bin/bash
set -u
mkdir -p /app/environment/systemd /app/environment/etc/collector /app/environment/etc/tmpfiles.d /app/environment/generated /app/output
cat > /app/environment/systemd/collector.socket <<'UNIT'
[Unit]
Description=Telemetry Collector socket

[Socket]
ListenStream=/run/telemetry/collector.sock
SocketUser=collector-sink
SocketGroup=collector-sink
SocketMode=0660

[Install]
WantedBy=sockets.target
UNIT
cat > /app/environment/systemd/collector.service <<'UNIT'
[Unit]
Description=Telemetry Collector
Requires=network.target
Requires=collector.socket
After=collector.socket

[Service]
Type=simple
Sockets=collector.socket
Environment=COLLECTOR_SOCKET_MODE=systemd
ExecStart=/app/bin/collectorctl serve --config /app/environment/etc/collector/collector.yaml --socket-mode=systemd
Restart=on-failure
UNIT
cat > /app/environment/etc/collector/collector.yaml <<'YAML'
bind_path: /run/collector-fallback.sock
run_user: collector-sink
sink_owner: collector-sink
sink_path: /var/lib/telemetry/collector.ndjson
report_label: main-telemetry-collector
YAML
cat > /app/environment/etc/tmpfiles.d/collector.conf <<'CONF'
d /run/telemetry 0750 collector-sink collector-sink -
z /run/telemetry/collector.sock 0660 collector-sink collector-sink -
CONF
/app/bin/collectorctl manifest --root /app/environment --out /app/environment/generated/exporter.manifest
/app/bin/collectorctl lifecycle --root /app/environment --report /app/output/collector-compliance-report.json --trace /app/output/collector-runtime-trace.json >/dev/null
