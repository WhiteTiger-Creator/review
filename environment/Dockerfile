FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        curl \
        jq \
        netcat-openbsd \
        nginx \
        patch \
        procps \
        psmisc \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
        varnish \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
COPY verifier-wheels /verifier-wheels

RUN python3 -m venv /opt/verifier_venv \
    && /opt/verifier_venv/bin/pip install \
        --no-index \
        --find-links=/verifier-wheels \
        --require-hashes \
        --no-deps \
        -r /tmp/requirements.lock \
    && rm -rf /tmp/requirements.lock

COPY mirrorveil/policy /srv/mirrorveil/policy
COPY mirrorveil/bin /srv/mirrorveil/bin
COPY mirrorveil/build-cache-stack.sh /srv/mirrorveil/build-cache-stack.sh

COPY mirrorveil/vcl /srv/mirrorveil/vcl
COPY mirrorveil/nginx /srv/mirrorveil/nginx
COPY mirrorveil/runbooks /srv/mirrorveil/runbooks
COPY mirrorveil/examples /srv/mirrorveil/examples

RUN find /srv/mirrorveil -type f -exec sed -i 's/\r$//' {} +

RUN chmod 0755 \
        /srv/mirrorveil/bin/start-cache-stack \
        /srv/mirrorveil/bin/stop-cache-stack \
        /srv/mirrorveil/bin/reload-cache-policy \
        /srv/mirrorveil/bin/cache-control \
        /srv/mirrorveil/bin/inspect-cache \
        /srv/mirrorveil/bin/wait-for-cache \
        /srv/mirrorveil/bin/compute-vcl-label \
        /srv/mirrorveil/build-cache-stack.sh \
        /srv/mirrorveil/examples/seed-origins.sh \
        /srv/mirrorveil/examples/make-large-object.sh \
        /srv/mirrorveil/examples/verify-stack.sh \
    && chmod 0600 /srv/mirrorveil/policy/control.conf \
    && /srv/mirrorveil/examples/seed-origins.sh \
    && /srv/mirrorveil/examples/make-large-object.sh \
    && /srv/mirrorveil/build-cache-stack.sh

WORKDIR /srv/mirrorveil
