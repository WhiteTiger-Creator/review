# Uses Python slim for the pytest harness because there is no canonical Mono base image for this task.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    make=4.3-4.1 \
    mono-mcs=6.8.0.105+dfsg-3.3+deb12u1 \
    mono-runtime=6.8.0.105+dfsg-3.3+deb12u1 \
    python3-pytest=7.2.1-2 \
    tmux=3.3a-3 \
    util-linux=2.38.1-5+deb12u3 \
 && rm -rf /var/lib/apt/lists/*

COPY task_file /app/task_file

WORKDIR /app/task_file
CMD ["/bin/bash"]
