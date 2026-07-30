FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3=3.11.2-1+b1 python3-pip=23.0.1+dfsg-1 \
        graphviz=2.42.2-7+deb12u1 \
        bash=5.2.15-2+b10 \
        jq=1.6-2.1+deb12u2 \
        ca-certificates=20230311+deb12u1 \
        coreutils=9.1-1 \
        patch=2.7.6-7 \
        findutils=4.9.0-4 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        curl=7.88.1-10+deb12u15 \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/opa https://openpolicyagent.org/downloads/v0.68.0/opa_linux_amd64_static \
    && echo 'dfd5081fc6f930dfeaf2a225e31e616fc227dc0c7b43019b73d6f8fb8a1de1aa  /tmp/opa' | sha256sum -c - \
    && mv /tmp/opa /usr/local/bin/opa \
    && chmod 755 /usr/local/bin/opa

RUN groupadd -r policyuser && useradd -r -g policyuser -d /home/policyuser -m policyuser

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

COPY go.mod go.sum ./
RUN go mod download

COPY --chown=policyuser:policyuser app/ /app/
COPY --chown=policyuser:policyuser scripts/ /app/scripts/

RUN bash /app/scripts/build_binary.sh \
    && chmod +x /app/scripts/*.py /app/test-visible/*.sh \
    && opa check /app/opalib \
    && chown policyuser:policyuser /app/bin /app/bin/*

RUN mkdir -p /output /logs/verifier /logs/agent \
    && chown policyuser:policyuser /output /logs /logs/verifier /logs/agent /home/policyuser \
    && chmod a+rwX /logs /output

ENV TZ=UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    HOME=/home/policyuser \
    OPA_PATH=/usr/local/bin/opa \
    TOKEN_EVENTS=/app/data/events \
    TOKEN_CONFIG=/app/config \
    TOKEN_REGOLIB=/app/opalib \
    TOKEN_OUTPUT=/output

CMD ["sleep", "infinity"]
