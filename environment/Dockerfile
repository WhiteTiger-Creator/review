FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.12.3-0ubuntu2.1 \
    python3-venv=3.12.3-0ubuntu2.1 \
    python3-pip=24.0+dfsg-1ubuntu1.3 \
    tmux=3.4-1ubuntu0.1 \
    asciinema=2.4.0-1 \
    ca-certificates=20260601~24.04.1 \
    curl=8.5.0-2ubuntu10.11 \
    patch=2.7.6-7build3 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
ENV PATH=/opt/verifier/bin:${PATH}

RUN mkdir -p /app/output /app/environment

COPY . /app/environment

# Warm Maven plugin/deps for offline verifier rebuilds.
RUN mvn -q -f /app/environment/pom.xml -DskipTests package \
    && rm -rf /app/environment/target

CMD ["bash", "-lc", "mvn -q -f /app/environment/pom.xml package && java -jar /app/environment/target/marlin-engine.jar --lane chrono"]
