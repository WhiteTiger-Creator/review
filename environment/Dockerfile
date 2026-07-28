# GNU Awk has no language-family canonical image, so the canonical Debian runtime
# is used and the small gawk toolchain is installed from Debian packages.
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

LABEL org.opencontainers.image.title="soil profile inversion workspace" \
      org.opencontainers.image.version="1.0" \
      org.opencontainers.image.licenses="MIT"

RUN apt-get update \
    && apt-get install -y --no-install-recommends gawk sqlite3 python3 python3-pip python-is-python3 tmux asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    numpy==2.2.6 \
    scipy==1.15.3

COPY schema.sql /opt/soil/schema.sql
COPY --chmod=0755 load.sh /opt/soil/load.sh
COPY inputs/ /opt/soil/inputs/

RUN mkdir -p /app/data /app/src /app/bin \
    && /opt/soil/load.sh /app/data/soil.sqlite

COPY invert.awk /app/src/invert.awk
COPY --chmod=0755 soilfit /app/bin/soilfit

WORKDIR /app
