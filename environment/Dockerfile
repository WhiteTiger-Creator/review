FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c AS builder

WORKDIR /build
COPY protected/ceph_govern.cpp /build/ceph_govern.cpp
RUN sha256sum /build/ceph_govern.cpp | cut -d' ' -f1 > /build/ceph-govern.source.sha256 && \
    g++ -std=c++20 -O2 -Wall -Wextra -Werror /build/ceph_govern.cpp -o /build/ceph-govern

FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update && \
    apt-get install -y --no-install-recommends asciinema ca-certificates ceph-common coreutils python3 python3-pip python3-venv tmux && \
    rm -rf /var/lib/apt/lists/*

ENV TERM=xterm

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/requirements.lock && \
    rm /tmp/requirements.lock

WORKDIR /app

COPY --from=builder --chmod=0555 /build/ceph-govern /usr/local/bin/ceph-govern
COPY docs/ /opt/ceph-governance/docs/
COPY scenarios/ /opt/ceph-governance/scenarios/
COPY --from=builder --chmod=0444 /build/ceph-govern.source.sha256 /opt/ceph-governance/ceph-govern.source.sha256
COPY work/ /app/work/ceph/
RUN chmod 0555 /opt/ceph-governance /opt/ceph-governance/docs /opt/ceph-governance/scenarios /usr/local/bin/ceph-govern && \
    chmod 0444 /opt/ceph-governance/docs/*.txt /opt/ceph-governance/scenarios/* /opt/ceph-governance/ceph-govern.source.sha256 && \
    chmod 0644 /app/work/ceph/Makefile /app/work/ceph/etc/*.conf /app/work/ceph/src/backfill_governance.cpp && \
    make -C /app/work/ceph clean all && \
    chmod 0755 /app/work/ceph/bin/backfill-governance && \
    ceph-conf --conf /app/work/ceph/etc/ceph.conf --name osd.0 --lookup osd_max_backfills >/dev/null && \
    tmux -V >/dev/null && asciinema --version >/dev/null && python3 -c "import pytest" && \
    (ceph-govern >/dev/null 2>&1 || test "$?" -eq 64) && \
    install -d /app/output /logs/verifier && \
    sha256sum /usr/local/bin/ceph-govern /opt/ceph-governance/ceph-govern.source.sha256 /opt/ceph-governance/docs/*.txt /opt/ceph-governance/scenarios/* > /opt/ceph-governance/integrity.sha256 && \
    chmod 0444 /opt/ceph-governance/integrity.sha256 && \
    test ! -e /build/ceph_govern.cpp && test ! -e /tests && test ! -e /solution

CMD ["/bin/bash"]
