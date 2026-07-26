FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        python3=3.11.2-1+b1 \
        python3-venv=3.11.2-1+b1 \
        patch=2.7.6-7 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pytest-randomly==3.16.0
RUN ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest \
    && ln -sf /opt/verifier/bin/py.test /usr/local/bin/py.test

ENV PATH="/opt/verifier/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

RUN mkdir -p /app/environment /app/output /logs/verifier

COPY package.json package-lock.json /app/environment/
COPY tsconfig.json /app/environment/tsconfig.json
WORKDIR /app/environment
RUN npm ci

COPY lib /app/environment/lib
COPY enc /app/environment/enc
COPY est /app/environment/est
COPY mut /app/environment/mut
COPY run_fit /app/environment/run_fit
COPY run_cf /app/environment/run_cf
COPY data /app/environment/data
COPY docs /app/environment/docs
COPY fixtures /app/environment/fixtures

WORKDIR /app
ENV PATH="/opt/verifier/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

RUN pytest --version \
    && node --version \
    && /app/environment/node_modules/.bin/tsx --version \
    && test -f /app/environment/docs/pub_contract.md \
    && test -f /app/environment/fixtures/seed_layout.json
