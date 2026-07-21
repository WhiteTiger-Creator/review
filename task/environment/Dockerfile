FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema \
    tmux \
    curl \
    ca-certificates \
    bash \
    util-linux \
    sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    flask==3.1.0 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    requests==2.32.3

RUN curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

RUN useradd -r -M -s /usr/sbin/nologin cropd \
    && useradd -m -u 1000 -s /bin/bash agent

COPY server.py /opt/crop-planner/server.py
COPY ensure-crop-server.sh /usr/local/bin/ensure-crop-server.sh
COPY entrypoint.sh /usr/local/bin/task-entrypoint.sh

RUN chmod 750 /opt/crop-planner/server.py \
    && chown root:cropd /opt/crop-planner/server.py \
    && chmod +x /usr/local/bin/ensure-crop-server.sh /usr/local/bin/task-entrypoint.sh \
    && mkdir -p /app/output /var/lib/crop-planner /var/log/crop-planner /etc/crop-planner \
    && chown cropd:cropd /var/lib/crop-planner /var/log/crop-planner \
    && chmod 700 /var/lib/crop-planner /var/log/crop-planner \
    && printf '%s\n' \
        'MODEL_SECRET=crop_plan_m0d3l_2026' \
        'LOG_SECRET=crop_plan_l0g_2026' \
        > /etc/crop-planner/env \
    && chmod 400 /etc/crop-planner/env \
    && chown root:root /etc/crop-planner/env \
    && chown agent:agent /app/output \
    && echo 'agent ALL=(root) NOPASSWD: /usr/local/bin/ensure-crop-server.sh, /usr/local/bin/ensure-crop-server.sh --reset' \
        > /etc/sudoers.d/agent-crop-planner \
    && chmod 440 /etc/sudoers.d/agent-crop-planner

ENTRYPOINT ["/usr/local/bin/task-entrypoint.sh"]
CMD ["sleep", "infinity"]
USER agent
