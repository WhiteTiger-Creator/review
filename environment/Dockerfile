FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app/emberline

RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    tmux \
    asciinema \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/emberline-venv \
 && /opt/emberline-venv/bin/pip install --no-cache-dir \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5

COPY Makefile README.md ./
COPY src ./src
COPY scenarios ./scenarios

RUN make \
 && java -version \
 && make -v \
 && tmux -V \
 && asciinema --version \
 && /opt/emberline-venv/bin/python -c "import pytest; import ctrf"

CMD ["sleep", "infinity"]
