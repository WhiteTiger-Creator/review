FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

# Fully resolved verifier lock; --no-deps keeps installation deterministic.
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --no-deps \
        -r /tmp/requirements.lock

WORKDIR /app

COPY app/ /app/
RUN cp /app/workflow/export_report.py /app/workflow/.export_report.original \
    && chmod a-w /app/workflow/.export_report.original

# Persistence and escalation paths left behind on the data-store platform during the Vaultwatch
# intrusion: a rogue sync-automation key, a passwordless sudoers escalation, and a
# world-readable datastore query-signing key.
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh \
    && printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIH7pQ2mVc4tXbN9sKfWjLd0aRyEuZoPnT3xBvMqGhKlS ops-oncall@bastion\n' > /root/.ssh/authorized_keys \
    && printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJx4jTq0d6nUcy0dGkzsBv1qkNPjc3hAcVcbWlkfZ2Qq dbnode-sync-automation\n' >> /root/.ssh/authorized_keys \
    && chmod 600 /root/.ssh/authorized_keys \
    && mkdir -p /etc/sudoers.d \
    && printf 'svc-dbnode ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/dbnode-sync \
    && chmod 0440 /etc/sudoers.d/dbnode-sync \
    && mkdir -p /app/secrets \
    && printf 'db-signing-synthetic-4c7e19b3f0a2-DO-NOT-USE\n' > /app/secrets/db_signing.key \
    && chmod 0644 /app/secrets/db_signing.key
