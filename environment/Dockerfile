FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14 AS gradle_deps

WORKDIR /tmp/deps
ARG GRADLE_VERSION=8.10.2
ARG GRADLE_SHA256=31c55713e40233a8303827ceb42ca48a47267a0ad4bab9177123121e71524c26
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl=7.81.0-1ubuntu1.25 \
    ca-certificates=20260601~22.04.1 \
    unzip=6.0-26ubuntu3.2 \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" -o /tmp/gradle.zip \
    && echo "${GRADLE_SHA256}  /tmp/gradle.zip" | sha256sum -c - \
    && unzip -q /tmp/gradle.zip -d /opt \
    && ln -s "/opt/gradle-${GRADLE_VERSION}" /opt/gradle \
    && rm -f /tmp/gradle.zip

ENV PATH="/opt/gradle/bin:${PATH}" \
    GRADLE_USER_HOME=/opt/gradle-cache-template

COPY pkg-seed/common/ /tmp/deps/pkg/
COPY app/release-mirror/ /tmp/deps/release-mirror/

RUN gradle --project-dir /tmp/deps/pkg --no-daemon dependencies \
    && gradle --project-dir /tmp/deps/pkg --no-daemon assemble -x test \
    && gradle --project-dir /tmp/deps/release-mirror --no-daemon dependencies \
    && gradle --project-dir /tmp/deps/release-mirror --no-daemon jar \
    && rm -rf /tmp/deps/pkg/build \
              /tmp/deps/pkg/*/build \
              /tmp/deps/release-mirror/build \
              /tmp/deps/pkg/.gradle \
              /tmp/deps/release-mirror/.gradle \
    && find /opt/gradle /opt/gradle-cache-template -type d -exec chmod a+rx {} + \
    && find /opt/gradle /opt/gradle-cache-template -type f -exec chmod a+r {} +

FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git=1:2.34.1-1ubuntu1.17 \
    curl=7.81.0-1ubuntu1.25 \
    ca-certificates=20260601~22.04.1 \
    jq=1.6-2.1ubuntu3.2 \
    python3=3.10.6-1~22.04.1 \
    python3-pip=22.0.2+dfsg-1ubuntu0.7 \
    tmux=3.2a-4ubuntu0.2 \
    asciinema=2.1.0-1 \
    procps=2:3.3.17-6ubuntu2.1 \
    netcat-openbsd=1.218-4ubuntu1 \
    openssl=3.0.2-0ubuntu1.26 \
    patch=2.7.6-7build2 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock
RUN rm -f /tmp/requirements.lock

# Build-context placeholders under environment/opt/* satisfy static COPY-source
# resolution for absolute --from sources; runtime bytes still come from gradle_deps.
COPY --from=gradle_deps /opt/gradle /opt/gradle
COPY --from=gradle_deps /opt/gradle-8.10.2 /opt/gradle-8.10.2
COPY --from=gradle_deps /opt/gradle-cache-template /opt/gradle-cache-template
RUN ln -sfn /opt/gradle-8.10.2 /opt/gradle \
    && find /opt/gradle /opt/gradle-cache-template -type d -exec chmod a+rx {} + \
    && find /opt/gradle /opt/gradle-cache-template -type f -exec chmod a+r {} +

COPY app/ /app/
COPY pkg-seed/ /opt/pkg-seed/
COPY bootstrap-app-repository.sh bootstrap-visible-fixtures.sh /tmp/
COPY data/ /tmp/seed-data/

RUN chmod +x /tmp/bootstrap-app-repository.sh /tmp/bootstrap-visible-fixtures.sh \
    && mkdir -p /data /app/.cache \
    && cp -a /app/pkg/ops /tmp/pkg-ops \
    && SEED_ROOT=/opt/pkg-seed /tmp/bootstrap-app-repository.sh /app/pkg \
    && mkdir -p /app/pkg/ops \
    && cp -a /tmp/pkg-ops/. /app/pkg/ops/ \
    && SCHEMA_SRC=/tmp/seed-data/run_callback.schema.strict.json DEST=/data /tmp/bootstrap-visible-fixtures.sh \
    && if [ -d /tmp/seed-data/manual-fragments ]; then \
         mkdir -p /app/docs/manual-fragments; \
         cp -a /tmp/seed-data/manual-fragments/. /app/docs/manual-fragments/; \
       fi \
    && test -f /app/docs/graph-run-signer-operations-manual.md \
    && test ! -f /app/pkg/config/signing-policy.yaml \
    && test -f /data/mlflow-release/mlflow-2.16.2.tar.gz \
    && test -f /data/keys/signer-2026.pk8 \
    && find /data/runs /data/mlflow-release /opt/pkg-seed /opt/gradle /opt/gradle-cache-template -type d -exec chmod a+rx {} + \
    && find /data/runs /data/mlflow-release /opt/pkg-seed /opt/gradle /opt/gradle-cache-template -type f -exec chmod a+r {} + \
    && chmod 600 /data/keys/*.pk8 \
    && chmod 644 /data/keys/*.pub \
    && chmod +x /app/pkg/ops/*.sh \
    && rm -rf /tmp/bootstrap-app-repository.sh /tmp/bootstrap-visible-fixtures.sh \
              /tmp/seed-data /tmp/pkg-ops

# Harbor/Daytona mounts /logs, /tests, /solution, and /output at runtime — do
# not pre-create those paths (EnvironmentStartTimeoutError). Stay root (no USER
# agent / useradd). Clear any inherited base-image ENTRYPOINT (Temurin
# /__cacert_entrypoint.sh) so writable mounts can finish under sleep.
RUN git config --global --add safe.directory /app/pkg \
    && git config --system --add safe.directory /app/pkg

ENV GRADLE_USER_HOME=/tmp/graphrun-gradle \
    GRADLE_BIN=/opt/gradle/bin/gradle \
    GRADLE_CACHE_TEMPLATE=/opt/gradle-cache-template \
    GRAPHRUN_POLICY=/app/pkg/config/signing-policy.yaml \
    GRAPHRUN_KEY_ROOT=/data/keys \
    GRAPHRUN_RUN_ROOT=/data/runs \
    GRAPHRUN_OUTPUT=/output \
    GRAPHRUN_LISTEN=127.0.0.1:18082 \
    GRAPHRUN_REPO=/app/pkg \
    MLFLOW_RELEASE_URL=http://127.0.0.1:18081/releases/mlflow-2.16.2.tar.gz \
    MLFLOW_RELEASE_SHA256_FILE=/data/mlflow-release/mlflow-2.16.2.sha256 \
    MLFLOW_RELEASE_CACHE=/app/.cache/mlflow-release \
    MLFLOW_RELEASE_DATA=/data/mlflow-release \
    TZ=UTC \
    LC_ALL=C.UTF-8 \
    PATH="/opt/gradle/bin:${PATH}"

WORKDIR /app

ENTRYPOINT []
CMD ["sleep", "infinity"]
