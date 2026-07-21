Automated frontend checks load /app/www/app.js in a minimal QuickJS DOM mock, not a full browser. The mock is incomplete compared to Chrome.

Do not use element.dataset or element.classList; use getAttribute and setAttribute for data attributes, and className (or split className on spaces) for classes. After HTML is rendered into notes-list, elements inside that container do not expose parentNode, closest, querySelector, or getElementsByTagName. Edit and delete handlers must read note id and any other needed fields from getAttribute on the clicked edit-btn or delete-btn. Per-button click listeners that close over the note object are fine.

Load the note list when the script first runs (top-level code), not only after window load or DOMContentLoaded. Use class names edit-btn and delete-btn on row buttons. Hook form submit with addEventListener on the element with id note-form. For edit and delete, attach per-button click listeners, or delegate clicks on notes-list or document only if the handler reads note data from the clicked button itself; relying only on window load handlers will not exercise the script.

Mutating fetch calls must send Content-Type: application/json even for DELETE. Form submissions must send JSON bodies built from the note-title and note-content field values with keys title and content, not empty or hard-coded placeholders.

The harness seeds GET /api/notes with two notes: title Note One with content Body One, and title Note Two with content Body Two. Other strings used during checks are arbitrary labels for form fields or API bodies only, including Find Me, In the List, Single Fetch, Updated Name, Updated Title, Echo Title, Echo Body, Edited body, E2E Create, and Note B Updated. Snapshots may expose listChildren as a read-only rendered-row count.

Verifier-side Python harness code for this app may import urllib for HTTP probes, signal for subprocess timing, and quickjs to execute app.js in the mock DOM.

The mock fetch implementation exposes json() on responses; prefer json() over text() for parsing bodies. Async patterns must complete within the mock job loop so post-mutation refreshes and form clearing actually run.
