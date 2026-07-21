FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.5a-3 \
        asciinema=2.4.0-1 \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc=4:14.2.0-1 \
    make-guile=4.4.1-2 \
    libmicrohttpd-dev=1.0.1-4 \
    libsqlite3-dev=3.46.1-7+deb13u1 \
    libcjson-dev=1.7.18-3.1+deb13u1 \
    curl=8.14.1-2+deb13u3 \
    file=1:5.46-5 \
    && rm -rf /var/lib/apt/lists/*

COPY verifier-requirements.txt /opt/verifier-requirements.txt

RUN python3 -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    pytest-timeout==2.3.1 \
    quickjs==1.19.4

WORKDIR /app

RUN mkdir -p /app/data /logs/verifier

COPY data/app/ /app/

CMD ["/bin/bash"]
