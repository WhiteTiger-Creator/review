# Build notes

The notes service links against libmicrohttpd and SQLite. Install the dev packages
for those libraries, then run `make` from `/app` to produce `notes_server`.

Web assets live under `/app/www` and are served from the HTTP root by URL path
(for example `/style.css` and `/app.js`).

Automated verifier traffic uses http://127.0.0.1:8080 as the base URL. Collection
health checks call http://127.0.0.1:8080/api/notes. Python verifier harnesses may
use urllib for HTTP, signal for subprocess timing, and quickjs when executing app.js.
