FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS go-toolchain

# The Spring Boot fixture is compiled and split into runtime layers here.
# JVM image justification: this task must compile Kotlin 1.9 and build/run a Spring Boot fixture with JDK 21.
# No smaller canonical t-bench runtime provides that toolchain, so the official public-ECR Eclipse Temurin image is used with an immutable digest.
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14 AS api-builder

ARG GRADLE_VERSION=8.10.2
ARG GRADLE_SHA256=31c55713e40233a8303827ceb42ca48a47267a0ad4bab9177123121e71524c26
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl unzip \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" -o /tmp/gradle.zip \
 && echo "${GRADLE_SHA256}  /tmp/gradle.zip" | sha256sum -c - \
 && unzip -q /tmp/gradle.zip -d /opt \
 && rm /tmp/gradle.zip
ENV PATH="/opt/gradle-${GRADLE_VERSION}/bin:${PATH}"
WORKDIR /build/inspection-api
COPY inspection-api/settings.gradle.kts inspection-api/build.gradle.kts ./
COPY inspection-api/src/ ./src/
RUN gradle --no-daemon --stacktrace bootJar \
 && mkdir -p /build/inspection-api/layers \
 && cd /build/inspection-api/layers \
 && java -Djarmode=layertools -jar ../build/libs/inspection-api-1.0.0.jar extract \
 && rm ../build/libs/inspection-api-1.0.0.jar

# The same justified JDK 21 base is required at runtime because the agent must compile
# the submitted Kotlin scientific analysis and launch the Spring Boot inspection service.
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

ARG KOTLIN_VERSION=1.9.25
ARG KOTLIN_SHA256=6ab72d6144e71cbbc380b770c2ad380972548c63ab6ed4c79f11c88f2967332e
COPY requirements.lock /tmp/requirements.lock
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      asciinema \
      ca-certificates \
      curl \
      jq \
      procps \
      python3 \
      python3-pip \
      sqlite3 \
      tmux \
      unzip \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL "https://github.com/JetBrains/kotlin/releases/download/v${KOTLIN_VERSION}/kotlin-compiler-${KOTLIN_VERSION}.zip" -o /tmp/kotlin.zip \
 && echo "${KOTLIN_SHA256}  /tmp/kotlin.zip" | sha256sum -c - \
 && unzip -q /tmp/kotlin.zip -d /opt \
 && mv /opt/kotlinc /opt/kotlin \
 && rm /tmp/kotlin.zip \
 && python3 -m pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
 && rm /tmp/requirements.lock

WORKDIR /app
COPY inspection-api/settings.gradle.kts inspection-api/build.gradle.kts /app/inspection-api/
COPY --from=go-toolchain /usr/local/go/ /usr/local/go/
ENV PATH="/usr/local/go/bin:/opt/kotlin/bin:${PATH}"
COPY inspection-api/src/ /app/inspection-api/src/
COPY app/ /app/
COPY --from=api-builder /build/inspection-api/layers/dependencies/ /opt/inspection-api/
COPY --from=api-builder /build/inspection-api/layers/spring-boot-loader/ /opt/inspection-api/
COPY --from=api-builder /build/inspection-api/layers/snapshot-dependencies/ /opt/inspection-api/
COPY --from=api-builder /build/inspection-api/layers/application/ /opt/inspection-api/
RUN chmod 0755 /app/bin/* \
 && /app/bin/rebuild-analyzer \
 && mkdir -p /app/output
