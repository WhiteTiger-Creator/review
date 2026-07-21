The Go job queue REST API at `/app` has multiple bugs causing endpoints to deviate from their specification. The authoritative spec is `/app/api_contract.json` — any endpoint behaviour that contradicts it is a bug. Fix the service so all endpoints conform to the contract.

The service manages batch jobs and workers backed by a SQLite database at `/opt/jobqueue/jobs.db`. Source files: `main.go` (routing and server startup), `service.go` (business logic and database queries), `handlers.go` (request/response wiring), `worker.go` (background worker pool), `models.go` (type definitions), `database.go` (schema and seed data). The database is pre-seeded with three workers (id=1 `worker-alpha`, id=2 `worker-beta`, id=3 `worker-gamma`) and six jobs: id=1 email/completed/priority=5/worker=1, id=2 report/running/priority=3/worker=2, id=3 image_resize/pending, id=4 email/pending/priority=2, id=5 data_export/failed/priority=1/worker=1, id=6 notification/pending/priority=4.

Requirements the system must satisfy:

- `POST /jobs` must return HTTP 201 on success with the created job object in the response body; the new job must have `status='pending'` and `worker_id=null`
- `POST /workers/register` must return HTTP 201 on success with the new worker object
- Jobs follow the state progression pending → running → completed or failed
- Only pending jobs may be cancelled; any other state must return 409
- Cancelled jobs must remain cancelled and must not transition to any other state
- The background worker pool must automatically pick up and process pending jobs without manual intervention; the pool must NOT write `worker_id` when claiming a job — pool-processed jobs retain `worker_id=null` throughout their lifecycle
- Every `GET /jobs/:id` response must include a `worker_name` field populated from the workers table when a worker is assigned; jobs with no assigned worker must return an empty string for this field
- The runtime configuration at `/opt/jobqueue/worker_config.json` must not cause cancelled jobs to change state
- `GET /stats` must return an object with integer fields for all five statuses: `pending`, `running`, `completed`, `failed`, `cancelled`

Do not modify `/app/api_contract.json` or any test files. Do not register a worker named `worker-delta` — that name is reserved by the test suite.
