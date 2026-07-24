# Canonical Maven + Temurin JDK 21 image on Ubuntu 24.04, pinned to the multi-arch manifest digest.
FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

ENV DEBIAN_FRONTEND=noninteractive

# Install terminal utilities and the Python runtime the tooling below needs.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates=20260601~24.04.1 \
      python3=3.12.3-0ubuntu2.1 \
      python3-venv=3.12.3-0ubuntu2.1 \
      tmux=3.4-1ubuntu0.1 \
      asciinema=2.4.0-1 \
 && rm -rf /var/lib/apt/lists/*

# Install the Python verifier dependencies (pytest, a CTRF reporter, and a crypto library) into a
# venv. These are generic test tooling only; the grading logic lives under /tests, which is mounted
# at verify time and is never part of this image.
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
 && rm -f /tmp/requirements.lock

WORKDIR /app

COPY microprofile-jwt-auth /app/microprofile-jwt-auth
COPY unsealer /app/unsealer

# Warm the local repository: install the MicroProfile JWT API from source, then run one complete
# build of the stub module so every plugin and dependency the inbox build needs is already on disk.
RUN mvn -B -q -f /app/microprofile-jwt-auth/pom.xml -pl api -am install -DskipTests \
 && mvn -B -q -f /app/unsealer/pom.xml clean package \
 && rm -rf /app/unsealer/target

COPY settings.xml /root/.m2/settings.xml
