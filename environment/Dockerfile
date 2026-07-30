FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    TERM=xterm-256color \
    PATH=/app/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONPATH=/opt/harbor-verifier

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        adduser \
        asciinema \
        bash \
        ca-certificates \
        coreutils \
        curl \
        gawk \
        grep \
        jq \
        python3 \
        python3-pytest \
        sed \
        sqlite3 \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && /usr/sbin/addgroup --system relay \
    && /usr/sbin/adduser --system --ingroup relay --no-create-home --home /nonexistent --shell /usr/sbin/nologin relayops

COPY harbor_ctrf_plugin.py /opt/harbor-verifier/harbor_ctrf_plugin.py
COPY prebuilt/harbor-relay /app/bin/harbor-relay
COPY prebuilt/catalog-query /app/bin/catalog-query
COPY prebuilt/service-catalog.db /opt/harbor/service-catalog.db
COPY prebuilt/maintenance-window.db /opt/harbor/maintenance-window.db
COPY app/include/ /opt/harbor-platform-source/include/
COPY app/src/ /opt/harbor-platform-source/src/
COPY app/tools/ /opt/harbor-platform-source/tools/
COPY app/docs/ /app/docs/
COPY app/records/ /app/records/
COPY app/fixtures/ /app/fixtures/
COPY app/etc/ /app/etc/
COPY app/share/ /app/share/
COPY app/scripts/ /app/scripts/

RUN install -m 0755 /app/bin/catalog-query /usr/local/bin/catalog-query \
    && chmod 0755 /app/bin/harbor-relay /app/bin/catalog-query /app/scripts/initialize-service-instance /app/scripts/exercise-service \
    && chmod 0444 /opt/harbor/service-catalog.db /opt/harbor/maintenance-window.db \
    && find /opt/harbor-platform-source -type f -exec chmod 0444 {} + \
    && find /app/docs /app/records /app/fixtures /app/share -type f -exec chmod 0444 {} + \
    && test "$(sha256sum /app/fixtures/requests/arrival-replay.http | awk '{print $1}')" = "1952a39bd9edfe4868259d14675eb5219ef6f21afe4854ee3e91b0c8c4ea5795" \
    && mkdir -p /app/run/harbor-relay /app/var /etc/systemd/system \
    && chown relayops:relay /app/run/harbor-relay /app/var \
    && chmod 0750 /app/run/harbor-relay /app/var \
    && chmod g-s /app/run/harbor-relay /app/var \
    && chown root:relay /app/etc/harbor-relay \
    && chmod 0750 /app/etc/harbor-relay \
    && tmux -V \
    && asciinema --version \
    && tmux -L harbor-runtime-smoke new-session -d -s smoke "sleep 30" \
    && tmux -L harbor-runtime-smoke has-session -t smoke \
    && tmux -L harbor-runtime-smoke kill-server \
    && bash /app/scripts/initialize-service-instance \
    && /app/bin/catalog-query --batch-file /app/share/service-catalog.batch > /tmp/service-catalog.snapshot \
    && HARBOR_CATALOG_DB=/opt/harbor/maintenance-window.db /app/bin/catalog-query --batch-file /app/share/maintenance-window.batch > /tmp/maintenance-window.snapshot \
    && sh -c '/app/bin/harbor-relay --help > /tmp/harbor-relay.help 2>&1; rc=$?; test "$rc" -eq 78' \
    && rm -f /tmp/service-catalog.snapshot /tmp/maintenance-window.snapshot /tmp/harbor-relay.help \
    && chown root:relay /app/etc/harbor-relay/relay.conf /app/etc/harbor-relay/limits.conf /app/etc/harbor-relay/routes.map

WORKDIR /app
