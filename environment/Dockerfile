FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        bash python3 python3-pip tmux util-linux asciinema \
 && rm -rf /var/lib/apt/lists/*

COPY wheels/ /opt/wheels/
RUN pip3 install --no-cache-dir --break-system-packages \
    --no-index --find-links /opt/wheels/ \
    pytest==8.2.2 pytest-json-ctrf==0.3.5

COPY app/ /app/

RUN node --experimental-strip-types --check /app/src/topple.ts \
 && node --experimental-strip-types --check /app/src/main.ts
# bust 2026-07-28 reroll tb_check
