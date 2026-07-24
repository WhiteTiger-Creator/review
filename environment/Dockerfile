FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip \
        make \
    && pip3 install --no-cache-dir --break-system-packages pytest==8.3.4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY main.go /app/main.go
COPY select.go /app/select.go
COPY go.mod /app/go.mod
COPY docs/ /app/docs/
COPY data/ /app/data/
COPY Makefile /app/Makefile
