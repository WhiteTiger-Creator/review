# Runtime layout

The notes service runs from `/app` with these primary paths:

- `notes_server` — HTTP daemon binary produced by `make`
- `src/` — C sources for libmicrohttpd routing and SQLite access
- `www/` — browser assets served at the HTTP root (`/`, `/style.css`, `/app.js`)
- `config/api.key` — optional API key read by the server
- `data/notes.db` — SQLite database created at runtime under `/app/data`
