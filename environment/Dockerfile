FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update && apt-get install -y --no-install-recommends \
    git=1:2.39.5-0+deb12u3 \
    gpg=2.2.40-1.1+deb12u2 \
    gpg-agent=2.2.40-1.1+deb12u2 \
    make=4.3-4.1 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.lock /tmp/verifier-requirements.txt
RUN python3 -m venv /opt/verifier \
 && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps \
      -r /tmp/verifier-requirements.txt

ENV PATH=/opt/verifier/bin:/usr/local/go/bin:${PATH}

COPY BUILD.md Makefile go.mod go.sum /app/environment/
COPY cmd/ /app/environment/cmd/
COPY docs/ /app/environment/docs/
COPY fixtures/ /app/environment/fixtures/
COPY k2/ /app/environment/k2/
COPY lib/ /app/environment/lib/
COPY p7/ /app/environment/p7/
COPY policy/ /app/environment/policy/
COPY q4/ /app/environment/q4/
COPY scripts/ /app/environment/scripts/

RUN mkdir -p /app/output /app/policy \
 && cp -r /app/environment/policy/* /app/policy/ \
 && cd /app/environment \
 && bash scripts/build_fixtures.sh \
 && cp -r /app/environment/policy/* /app/policy/ \
 && make build

WORKDIR /app
