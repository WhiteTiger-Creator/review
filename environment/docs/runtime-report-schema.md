# Runtime report schema

`collectorctl manifest --root <root> --out <manifest>` writes a key=value manifest.
`collectorctl lifecycle --root <root> --report <report> --trace <trace>` writes the compliance report and runtime trace.  These flags are the normal replay interface for the visible operational authority set.

The manifest schema is `telemetry.collector.exporter.v2` and includes `authority`, `socket_path`, `socket_user`, `socket_group`, `socket_mode`, `service_socket`, `service_socket_mode`, `tmpfiles_socket_owner`, `tmpfiles_socket_group`, `tmpfiles_socket_mode`, `sink_owner`, `source_digest`, and `provenance` keys.  The generated manifest uses `provenance=regenerated-from-visible-authorities`.

The compliance report contains `ok`, `runtime`, `manifest`, `lifecycle`, `checks`, `notes`, and `report_digest`.  The `runtime` object contains `authority`, `socket_path`, `socket_owner`, `socket_group`, `socket_mode`, `service_sockets`, and `service_socket_mode`.  The `manifest` object contains `consistent`, `path`, `values`, and `provenance`.  Satisfied replay booleans are `true`: `ok`, `consistent`, `generated_manifest_current`, `runtime_socket_matches_manifest`, `socket_owned_by_collector_sink`, `tmpfiles_preserve_socket_owner`, `service_binds_declared_socket`, `main_systemd_socket_authority`, `main_socket_mode_expected`, `tmpfiles_directory_owned`, `lifecycle_socket_inode_stable`, `legacy_yaml_fallback_allowed`, and `legacy_fallback_path_present`.

The lifecycle phase list is daemon-reload, first-activation, service-restart, sink-rotation, and report-regeneration.  All phases share one `socket_inode` value when the runtime socket identity is stable.  The runtime trace contains `runtime_socket`, `authority_trace`, `phases`, and `stable_inode`; `stable_inode` is `true` for a successful replay.  Temporary comparison files may use names such as expected.manifest, first-report.json, first-trace.json, second-report.json, and second-trace.json during local replay.

Compatibility replay for `/app/environment/fixtures/legacy-root` uses `/run/legacy-collector.sock` as the yaml fallback socket path.  Successful main replay has exactly `1` distinct `socket_inode` value across all lifecycle phases.
