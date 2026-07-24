# Canonical Terminal-Bench Java JDK 21 base (docs/PLATFORM_AUTO_EVAL.md).
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends python3=3.10.6-1~22.04.1 python3-venv=3.10.6-1~22.04.1 make=4.3-4.1build1 tmux=3.2a-4ubuntu0.2 asciinema=2.1.0-1 ca-certificates=20260601~22.04.1 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
       pytest==8.4.1 \
       pytest-json-ctrf==0.3.5 \
       pytest-randomly==3.16.0

ENV PATH=/opt/verifier/bin:${PATH}

RUN mkdir -p /app/exec /app/output /app/environment

COPY . /app/environment

RUN cp /app/environment/exec/diff_run /app/exec/diff_run \
    && chmod +x /app/exec/diff_run /app/environment/app/tools/inspect.sh

ENV JAVA_HOME=/opt/java/openjdk
