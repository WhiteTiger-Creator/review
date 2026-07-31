FROM public.ecr.aws/docker/library/ruby:3.3-slim-bookworm@sha256:e76733e94b3a5893e4a141024ef3a583dc10781dc24becebf74f9c9f9a33e3df

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        bash python3 python3-pip tmux util-linux asciinema \
 && rm -rf /var/lib/apt/lists/*

COPY wheels/ /opt/wheels/
RUN pip3 install --no-cache-dir --break-system-packages \
    --no-index --find-links /opt/wheels/ \
    pytest==8.2.2 pytest-json-ctrf==0.3.5

RUN mkdir -p /logs/verifier

COPY app/ /app/

RUN ruby -c /app/warband.rb \
 && ruby -c /app/main.rb
