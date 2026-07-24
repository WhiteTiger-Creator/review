# Canonical Java (JDK) runtime base per docs/PLATFORM_AUTO_EVAL.md (Edition 2).
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.10.6-1~22.04.1 \
    python3-venv=3.10.6-1~22.04.1 \
    tmux=3.2a-4ubuntu0.2 \
    asciinema=2.1.0-1 \
    ca-certificates=20260601~22.04.1 \
    maven=3.6.3-5 \
    patch=2.7.6-7build2 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5 \
      pyyaml==6.0.2

ENV PATH=/opt/verifier/bin:${PATH}
ENV MAVEN_OPTS="-Dmaven.repo.local=/opt/m2"

COPY . /app/environment

RUN mkdir -p /opt/m2 /app/output \
    && chmod +x /app/environment/scripts/*.sh \
    && cd /app/environment \
    && mvn -Dmaven.repo.local=/opt/m2 -q -DskipTests package

WORKDIR /app
