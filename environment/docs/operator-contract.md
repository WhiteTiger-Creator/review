# Telemetry Collector operator contract

The operator command records the socket authority declared by the environment.
When a `collector.socket` unit exists, the unit is the active authority and the
configuration path is only a fallback.  Without that unit, the configuration path
remains authoritative for legacy roots.

The runtime image stores the built operator digest at `/app/environment/var/lib/collectorctl.sha256` so operators can confirm the recorder identity remains stable.
