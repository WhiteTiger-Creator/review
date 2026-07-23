# syntax=docker/dockerfile:1

FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14 AS maven_warm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends maven=3.6.3-5 && rm -rf /var/lib/apt/lists/*

WORKDIR /warm
COPY app/pom.xml .
COPY app/src/ /warm/src/

RUN mvn -B -q -Dmaven.repo.local=/opt/m2/repository \
        dependency:go-offline \
        dependency:resolve-plugins -DincludePluginsFromSuperPom=true \
    && mvn -B -q -Dmaven.repo.local=/opt/m2/repository \
        resources:resources compiler:compile resources:testResources compiler:testCompile \
        surefire:test -DskipTests \
        jar:jar shade:shade \
    && mvn -B -q -Dmaven.repo.local=/opt/m2/repository dependency:get \
        -Dartifact=org.apache.maven.surefire:surefire-junit-platform:3.2.5 \
    && mvn -B -q -Dmaven.repo.local=/opt/m2/repository dependency:get \
        -Dartifact=org.junit.platform:junit-platform-launcher:1.10.3

FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14 AS env

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends asciinema=2.1.0-1 ca-certificates=20240203~22.04.1 curl=7.81.0-1ubuntu1.23 jq=1.6-2.1ubuntu3.2 make=4.3-4.1build1 maven=3.6.3-5 python3=3.10.6-1~22.04.1 python3-pip=22.0.2+dfsg-1ubuntu0.7 tmux=3.2a-4ubuntu0.2 unzip=6.0-26ubuntu3.2 && rm -rf /var/lib/apt/lists/*

COPY verifier-requirements.txt /tmp/verifier-requirements.txt

# hadolint ignore=DL3013
RUN python3 -m pip install --no-cache-dir -r /tmp/verifier-requirements.txt \
    && rm -f /tmp/verifier-requirements.txt

ENV MAVEN_OPTS="-Dmaven.repo.local=/opt/m2/repository" \
    JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF-8" \
    HOME=/root \
    TRIVIA_ROOT=/app \
    TRIVIA_CONFIG=/app/config/dungeon.toml \
    TRIVIA_DATASET=/data/trivia_qa_sample.parquet \
    TRIVIA_CONTRACTS=/data/contracts \
    TRIVIA_STATE=/app/.state/audit-state.json

COPY --from=maven_warm /opt/m2/repository /opt/m2/repository

COPY app/pom.xml /app/pom.xml
WORKDIR /app
COPY app/ /app/

RUN mkdir -p /app/bin \
    && printf '%s\n' '#!/bin/sh' 'set -eu' 'APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"' 'JAR="$APP_DIR/target/trivia-dungeon-1.0.0-SNAPSHOT.jar"' 'if [ ! -f "$JAR" ]; then echo "trivia-dungeon: jar not built; run make build" >&2; exit 1; fi' 'exec java -jar "$JAR" "$@"' > /app/bin/trivia-dungeon \
    && chmod +x /app/bin/trivia-dungeon

COPY data/trivia_qa_sample.parquet /data/trivia_qa_sample.parquet
COPY contracts/ /data/contracts/

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN mkdir -p /output /app/.state /logs/verifier /logs/agent \
    && chmod 1777 /output /logs \
    && chmod -R a+rwX /app /opt/m2/repository \
    && chown -R root:root /data \
    && chmod -R a-w /data

WORKDIR /app

CMD ["sleep", "infinity"]
