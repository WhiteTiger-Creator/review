FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        sqlite3 \
        python3 \
        python3-pytest \
        ca-certificates \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json tsconfig.json ./
RUN npm ci --ignore-scripts

COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY schema/ /app/schema/
COPY seeds/ /app/seeds/
COPY evidence/ /app/evidence/
COPY docs/ /app/docs/
COPY ops/ /app/ops/

ENV NODE_ENV=production
WORKDIR /app
