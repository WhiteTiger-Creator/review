FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14 AS jdk-toolchain

RUN apt-get update \
    && apt-get install -y --no-install-recommends xz-utils \
    && rm -rf /var/lib/apt/lists/*

COPY vendor/kotlinc-2.1.0-jvm.tar.xz /tmp/kotlinc.tar.xz
RUN mkdir -p /opt/kotlinc \
    && tar -xJf /tmp/kotlinc.tar.xz -C /opt/kotlinc \
    && rm /tmp/kotlinc.tar.xz \
    && chmod 755 /opt/kotlinc/bin/kotlinc /opt/kotlinc/bin/kotlinc-jvm

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

COPY --from=jdk-toolchain /opt/java/openjdk /opt/java/openjdk
COPY --from=jdk-toolchain /opt/kotlinc /opt/kotlinc

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates coreutils diffutils \
       findutils grep sed util-linux tmux asciinema xz-utils \
    && rm -rf /var/lib/apt/lists/*

COPY vendor/pywheels.tar.xz /tmp/pywheels.tar.xz
COPY requirements.lock /tmp/requirements.lock
RUN mkdir -p /tmp/wheels \
    && tar -xJf /tmp/pywheels.tar.xz -C /tmp/wheels \
    && rm /tmp/pywheels.tar.xz \
    && pip install --no-cache-dir --no-index --find-links /tmp/wheels \
       --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -rf /tmp/wheels /tmp/requirements.lock

ENV JAVA_HOME=/opt/java/openjdk \
    PATH="/opt/java/openjdk/bin:/opt/kotlinc/bin:${PATH}"

RUN ln -s /opt/java/openjdk/bin/java /usr/local/bin/java \
    && ln -s /opt/java/openjdk/bin/javac /usr/local/bin/javac \
    && ln -s /opt/kotlinc/bin/kotlinc /usr/local/bin/kotlinc \
    && printf 'export JAVA_HOME=/opt/java/openjdk\nexport PATH="/opt/java/openjdk/bin:/opt/kotlinc/bin:$PATH"\n' \
       > /etc/profile.d/toolchain.sh

WORKDIR /app
COPY README.md ./README.md
COPY docs ./docs
COPY src ./src
COPY data ./data
COPY build.sh ./build.sh
COPY run.sh ./run.sh
RUN chmod 755 /app/build.sh /app/run.sh

RUN useradd -m -u 1000 -s /bin/bash agent \
    && chown -R agent:agent /app
