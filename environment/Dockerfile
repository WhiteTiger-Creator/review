# Canonical digest-pinned Ruby 3.3 image for the Crystal Cellar runner.
FROM public.ecr.aws/docker/library/ruby:3.3-slim-bookworm@sha256:e76733e94b3a5893e4a141024ef3a583dc10781dc24becebf74f9c9f9a33e3df

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash=5.2.15-2+b13 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        util-linux=2.38.1-5+deb12u3 \
        login=1:4.13+dfsg1-1+deb12u2 \
        git=1:2.39.5-0+deb12u3 \
        ripgrep=13.0.0-4+b2 \
        patch=2.7.6-7 \
        ca-certificates=20230311+deb12u1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --break-system-packages --require-hashes -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

WORKDIR /app
COPY repo/ /app/

RUN set -e; \
    ruby -c /app/bin/crystal-cellar-push; \
    find /app/lib -type f -name '*.rb' -print0 | xargs -0 -n1 ruby -c

RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"
