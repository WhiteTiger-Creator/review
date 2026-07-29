FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.12.3-0ubuntu2.1 \
    python3-venv=3.12.3-0ubuntu2.1 \
    python3-pip=24.0+dfsg-1ubuntu1.3 \
    tmux=3.4-1ubuntu0.1 \
    asciinema=2.4.0-1 \
    ca-certificates=20260601~24.04.1 \
    openssl=3.0.13-0ubuntu3.11 \
    libssl3t64=3.0.13-0ubuntu3.11 \
    patch=2.7.6-7build3 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pytest-randomly==3.16.0

RUN ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest

ENV PATH=/opt/verifier/bin:${PATH}
ENV MAVEN_OPTS="-Dmaven.repo.local=/root/.m2/repository"

COPY pom.xml /app/pom.xml
COPY r4 /app/r4
COPY p7 /app/p7
COPY v5 /app/v5
COPY t3 /app/t3
COPY q9 /app/q9
COPY m6 /app/m6
COPY w8 /app/w8
COPY tools /app/tools
COPY data /app/data
COPY docs /app/docs

RUN mvn -q -DskipTests package \
    && mkdir -p /app/output /app/bin \
    && printf '%s\n' '#!/bin/bash' 'exec java -jar /app/target/uxr-1.0.0.jar "$@"' > /app/bin/uxr \
    && chmod +x /app/bin/uxr
