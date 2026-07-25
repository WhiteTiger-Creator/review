# Relay configuration and route map

`relay.conf` is a newline-terminated key/value file with exactly these keys in order: `site_key`, `socket_path`, `socket_mode`, `socket_owner`, `socket_group`, `listen_backlog`, `route_map`, `limits_file`, `audit_db`, and `catalog_generation`. Paths are absolute. Socket modes are four octal digits. Unknown or duplicate keys are invalid.

`limits.conf` contains exactly `open_files_soft`, `reserved_files`, `max_connections`, and `request_body_limit` in that order. Values are unsigned decimal. `routes.map` is a sorted TSV with header `method external_path upstream auth_mode timeout_ms source_route_id` separated by tabs. Route keys are unique by method and path. All text files end in one newline.

`harbor-relay --check-config /absolute/staged/relay.conf` loads the referenced limits and route files and returns zero without binding a socket. Normal execution binds the selected Unix socket, ignores query parameters during route lookup, preserves the normalized path in its JSON response, returns 413 above the body limit, 404 for a missing route, and 200 for a matched route.
