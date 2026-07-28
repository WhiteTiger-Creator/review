FROM golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        g++ \
        make \
        python3 \
        python3-pip \
        python3-venv \
        sqlite3 \
        tmux; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

ENV TEST_VENV=/opt/test-venv
ENV PATH="${TEST_VENV}/bin:${PATH}"

RUN set -eux; \
    python3 -m venv "${TEST_VENV}"; \
    "${TEST_VENV}/bin/pip" install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        cryptography==43.0.3

ENV GOFLAGS=-mod=mod
ENV GOTOOLCHAIN=local

WORKDIR /app

RUN mkdir -p /app/output /app/trust-remediator/build

COPY data/              /app/data/
COPY operator_handbook/ /app/operator_handbook/
COPY trust-remediator/  /app/trust-remediator/

CMD ["/bin/bash"]
