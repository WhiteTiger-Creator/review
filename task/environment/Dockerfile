FROM golang:1.22-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc sqlite3 tmux curl python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages --no-cache-dir \
    pytest==8.4.1 pytest-json-ctrf==0.5.0 requests==2.32.3

WORKDIR /app

RUN mkdir -p /opt/jobqueue /logs/verifier

COPY task_file/ ./

# Ops config: auto_retry_cancelled is on from the last incident response.
# This is intentional — toggled by on-call, not application code.
RUN cp worker_config.json /opt/jobqueue/worker_config.json

RUN CGO_ENABLED=1 go build -mod=vendor -o jobqueue .

ENV DB_PATH=/opt/jobqueue/jobs.db
ENV PORT=8080

EXPOSE 8080
