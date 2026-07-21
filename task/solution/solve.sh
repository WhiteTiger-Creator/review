#!/bin/bash
set -euo pipefail

# Fix Bug 1: wrong column name 'job_type' in CreateJob INSERT
sed -i 's/INSERT INTO jobs (job_type, payload, priority)/INSERT INTO jobs (type, payload, priority)/' /app/service.go

# Fix Bug 2: wrong HTTP status code on job creation (200 → 201)
python3 - <<'PYEOF'
with open('/app/handlers.go') as f:
    src = f.read()

old = '''\tjob, err := h.svc.CreateJob(req)
\tif err != nil {
\t\twriteError(w, http.StatusInternalServerError, err.Error())
\t\treturn
\t}
\twriteJSON(w, http.StatusOK, job)
}'''
new = '''\tjob, err := h.svc.CreateJob(req)
\tif err != nil {
\t\twriteError(w, http.StatusInternalServerError, err.Error())
\t\treturn
\t}
\twriteJSON(w, http.StatusCreated, job)
}'''

assert old in src, "Bug 2 patch target not found in handlers.go"
with open('/app/handlers.go', 'w') as f:
    f.write(src.replace(old, new, 1))
PYEOF

# Fix Hidden Bug 5: disable the auto-requeue daemon in the ops config.
# startConfigWatcher in main.go reads this every 3 seconds; with
# auto_retry_cancelled=true it silently re-queues every cancelled job.
printf '{"max_workers":5,"auto_retry_cancelled":false}\n' \
    > /opt/jobqueue/worker_config.json

# Rebuild
cd /app && CGO_ENABLED=1 go build -mod=vendor -o jobqueue .

echo "all patches applied and binary rebuilt"
