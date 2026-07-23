FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        gfortran=4:12.2.0-3 \
        git=1:2.39.5-0+deb12u3 \
        make=4.3-4.1 \
        patch=2.7.6-7 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        ripgrep=13.0.0-4+b2 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir --break-system-packages --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

WORKDIR /app
COPY repo/ /app/

RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state" \
    && git config --system --add safe.directory /app
