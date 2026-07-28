# Relay service configuration format

`relay.conf` is newline-terminated and contains exactly these keys in order: `site_key`, `socket_path`, `socket_mode`, `socket_owner`, `socket_group`, `listen_backlog`, `route_map`, `limits_file`, `audit_db`, `catalog_generation`. Paths are absolute and socket mode is four octal digits. `socket_owner` and `socket_group` come from the selected enabled `deployment_context` row.

`limits.conf` contains exactly `open_files_soft`, `reserved_files`, `max_connections`, `request_body_limit` in that order. `routes.map` is a tab-separated file with header `method external_path upstream auth_mode timeout_ms source_route_id`; rows are sorted by method and external path.

`/app/run/harbor-relay` is the daemon runtime directory. It is owned by `relayops:relay`, has mode `0750` with no setgid bit, and contains only the active Unix socket while the service is running.

`/etc/systemd/system/harbor-relay.service` is a conventional unit with sections `[Unit]`, `[Service]`, and `[Install]`. The service properties are `Type=simple`, `User=relayops`, `Group=relay`, `ExecStart=/app/bin/harbor-relay --config /app/etc/harbor-relay/relay.conf`, `LimitNOFILE` equal to `open_files_soft`, `UMask=0007`, and `Restart=no`; it is wanted by `multi-user.target`.

The configuration must load through the existing relay. When launched as `relayops`, the daemon must bind the selected Unix socket, ignore query parameters during route lookup, return 200 for matched routes, 404 for an unknown route, and 413 when the request body exceeds `request_body_limit`.
