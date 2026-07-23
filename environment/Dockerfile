FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9 \
    ca-certificates=20230311+deb12u1 \
    cmake=3.25.1-1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY CMakeLists.txt /app/CMakeLists.txt
COPY src /app/src
COPY etc /app/etc
COPY usr /app/usr
COPY opt /app/opt
COPY tools /app/tools
COPY docs /app/docs
COPY fixtures /app/fixtures

RUN cmake -S /app -B /tmp/site-build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /tmp/site-build --parallel 2 \
    && cmake --install /tmp/site-build --prefix /app \
    && rm -rf /tmp/site-build \
    && chmod 0755 \
        /app/usr/sbin/site-admin \
        /app/usr/sbin/site-activate \
        /app/usr/libexec/a1/q1.sh \
        /app/usr/lib/b2/q2.sh \
        /app/opt/c3/exec/q3.sh \
        /app/usr/libexec/a1/r1.sh \
        /app/opt/c3/exec/r3.sh \
        /app/tools/make-lab.sh


# Offline verifier (task.toml: allow_internet=false): bake pytest at image build.
# terminus-2 drives the agent through an interactive tmux bash. Agents sometimes
# append `exit $rc` after builds; that tears down the session and yields
# verifier_did_not_run. Keep the shell alive under TMUX (harness teardown still
# uses tmux kill-session).
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    python-is-python3=3.11.2-1+deb12u1 \
    tmux=3.3a-3 asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/* \
    && command -v tmux && command -v asciinema \
    && tmux -V \
    && asciinema --version \
    && printf '%s\n' \
         '' \
         'if [ -n "${TMUX:-}" ]; then' \
         '  exit() { true; }' \
         'fi' >> /etc/bash.bashrc \
    && mkdir -p /root \
    && touch /root/.bashrc \
    && printf '%s\n' \
         '' \
         'if [ -n "${TMUX:-}" ]; then' \
         '  exit() { true; }' \
         'fi' >> /root/.bashrc \
    && python -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 pytest-json-ctrf==0.3.5 \
    && /opt/verifier-venv/bin/pytest --version \
    && ln -sf /opt/verifier-venv/bin/pytest /usr/local/bin/pytest
ENV PATH="/opt/verifier-venv/bin:${PATH}"
CMD ["sleep", "infinity"]
