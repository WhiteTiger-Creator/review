# Janet has no canonical language image, so its pinned source toolchain is built on canonical Debian.
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d AS janet-builder

ARG JANET_VERSION=1.41.2
ARG JANET_SHA256=168e97e1b790f6e9d1e43685019efecc4ee473d6b9f8c421b49c195336c0b725

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/janet
RUN curl --fail --location --silent --show-error \
        "https://github.com/janet-lang/janet/archive/refs/tags/v${JANET_VERSION}.tar.gz" \
        --output janet.tar.gz \
    && echo "${JANET_SHA256}  janet.tar.gz" | sha256sum --check - \
    && tar --extract --gzip --file janet.tar.gz --strip-components=1 \
    && make -j2 \
    && make install PREFIX=/usr/local DESTDIR=/janet-root

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

LABEL org.opencontainers.image.title="Enceladus plume inversion workspace" \
      org.opencontainers.image.version="2.0" \
      org.opencontainers.image.licenses="MIT"

RUN apt-get update \
    && apt-get install -y --no-install-recommends asciinema ca-certificates python3 python3-pip python-is-python3 sqlite3 tmux util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps --requirement /tmp/requirements.lock

COPY --from=janet-builder /janet-root/usr/local/ /usr/local/

WORKDIR /app
COPY src/ /app/src/
COPY input/ /app/input/
RUN mkdir -p /app/output
