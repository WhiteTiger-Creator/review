FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN rustup set profile minimal \
    && rustup toolchain install 1.89.0 \
    && rustup default 1.89.0 \
    && rustup toolchain uninstall 1.85.1 \
    && rm -rf /usr/local/cargo/git /usr/local/cargo/registry

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive
ENV RUSTFLAGS=-Awarnings
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH=/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       asciinema ca-certificates curl git python3 python3-pytest sqlite3 tmux \
    && rm -rf /var/lib/apt/lists/*

COPY --from=0 /usr/ /usr/
COPY --from=0 /etc/alternatives/ /etc/alternatives/
RUN ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -sf /usr/local/cargo/bin/rustup /usr/local/bin/rustup \
    && rustc --version \
    && cargo --version

WORKDIR /app
COPY tooling/ /app/tooling/
RUN set -eu; \
    case "$TARGETARCH" in \
      amd64) audit_arch=amd64; deny_arch=amd64; \
        audit_sha=1bc78e3a886203846d1f49efff2d8d97a02fc6cd74c271397c05cbe105568b1c; \
        deny_sha=46cd3e14d1f04b42313f368a59835d911c9221343eeca0010c57bd52d98387f1 ;; \
      arm64) audit_arch=arm64; deny_arch=arm64; \
        audit_sha=bc1528b7ba3b7dc0bb681eaa13237fb195142ef0ba037f0e73d28afc3ec22c4d; \
        deny_sha=2d73ad81fcff09a2c1b84217c15fd15b83eb09ce5a6a38ed3bf95de6b78b8977 ;; \
      *) echo "unsupported build architecture" >&2; exit 1 ;; \
    esac; \
    audit_file="/app/tooling/cargo-audit-${audit_arch}.bin"; \
    deny_file="/app/tooling/cargo-deny-${deny_arch}.bin"; \
    echo "${audit_sha}  ${audit_file}" | sha256sum -c -; \
    echo "${deny_sha}  ${deny_file}" | sha256sum -c -; \
    install -m 0755 "$audit_file" /usr/local/bin/cargo-audit; \
    install -m 0755 "$deny_file" /usr/local/bin/cargo-deny; \
    cargo audit --version; \
    cargo deny --version

COPY Cargo.toml Cargo.lock /app/
COPY .cargo/ /app/.cargo/
COPY vendor/ /app/vendor/
COPY crates/ /app/crates/
COPY docs/ /app/docs/
COPY sql/ /app/sql/
RUN cargo test --workspace --all-targets --locked --offline \
    && rm -rf /app/target

COPY . /app
CMD ["sleep", "infinity"]
