FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV PATH="/usr/local/go/bin:/usr/local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    asciinema \
    python3 \
    python3-pip \
    python-is-python3 \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && printf '%s\n' 'export PATH="/usr/local/go/bin:/usr/local/bin:$PATH"' > /etc/profile.d/go-path.sh \
    && chmod 644 /etc/profile.d/go-path.sh \
    && echo 'export PATH="/usr/local/go/bin:/usr/local/bin:$PATH"' >> /root/.bashrc \
    && echo 'export PATH="/usr/local/go/bin:/usr/local/bin:$PATH"' >> /root/.profile

WORKDIR /app

COPY go.mod /app/go.mod
COPY cmd/ /app/cmd/
COPY internal/ /app/internal/
COPY config/ /app/config/
COPY docs/ /app/docs/
COPY scenarios/ /app/scenarios/

RUN mkdir -p /app/bin /app/output \
    && go build -o /app/bin/hanabi ./cmd/hanabi

CMD ["sleep", "infinity"]
