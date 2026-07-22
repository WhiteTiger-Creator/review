FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         asciinema \
         ca-certificates \
         python3-numpy \
         python3-pandas \
         python3-pytest \
         python3-sklearn \
         r-base-core \
         r-cran-jsonlite \
         r-cran-mass \
         r-cran-nnet \
         tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p /app/data /app/output

COPY data/ /app/data/
COPY pytest_json_ctrf.py /app/pytest_json_ctrf.py
