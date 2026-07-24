# Base image (digest pre-pinned by the orchestrator; pasted verbatim): the canonical
# Java image. This task is Java/Maven/Lua, and the shipped image's base reflects that.
# The verifier and the sealed data service below both need a Python interpreter at
# runtime, but that's satisfied by apt-installing python3 on top (below), not by basing
# the final image on a Python-family image.
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14 AS sealed-builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
# Builder stage for the sealed data service: compiles sealed/data_service.py to
# bytecode-only. Its .py source is COPY'd here, in a stage that is discarded after the
# final image is built, so it never reaches the agent-visible image below — only the
# compiled .pyc does. That service is the only thing that ever reads the seed database
# contents and pinned Hugging Face config fixtures; see environment/sealed/data_service.py
# and com.example.registry.SealedDataService for the full rationale. This stage MUST use
# the exact same base image (and therefore the exact same apt python3 build) as the final
# stage below: .pyc bytecode is tied to the CPython minor version that compiled it, so
# compiling with a different Python version than the one that will run it at runtime
# silently fails to load.
COPY sealed/data_service.py /build/data_service.py
RUN python3 -c "\
import py_compile; \
py_compile.compile('/build/data_service.py', '/build/data_service.pyc', optimize=2)"

FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

# System packages: agent runtime (tmux, asciinema) + CA certs + Maven (the JDK is
# already the base image, via Temurin) + Python 3 (needed only for the verifier's
# pytest and to run the sealed data service's compiled bytecode; see
# environment/sealed/data_service.py). Single apt transaction, --no-install-recommends,
# lists cleaned in the same layer. Native lua5.4 is deliberately NOT installed — the Lua
# bridge runs in-JVM via org.luaj:luaj-jse. apt versions are intentionally unpinned:
# Ubuntu jammy prunes point-release versions from its repos as security updates land, so
# exact pins (e.g. maven=3.6.3-5) break the build over time. The pinned base-image
# digest already fixes the snapshot.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        maven \
        python3 \
        python3-pip \
        python-is-python3 \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Python deps — pinned. tests/test.sh (outside this Dockerfile's control) invokes the
# bare `python -m pytest --ctrf …` directly in this image (shared mode); Ubuntu's
# python3 package doesn't provide a `python` symlink on its own the way Debian's did on
# the old base, hence python-is-python3 above. pytest + pytest-json-ctrf must be baked in.
RUN python3 -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

# Copy the whole harness subtree so its root IS the workdir. After this,
# /app/pom.xml, /app/migrations/, /app/expected/, and /app/mlflow_registry_bundle.tar.gz
# all exist. The harness ships a .gitignore excluding target/, so no build output is copied.
COPY harness/ /app/

# The sealed data service: compiled-only (no .py source anywhere in this image), started
# lazily by SealedDataService.java the first time SeedDatabaseLoader/HubConfigClient need
# it. Lives outside /app entirely, so it's outside the tree the agent edits/inspects.
COPY --from=sealed-builder /build/data_service.pyc /opt/_sealed/data_service.pyc

# Pre-warm the Maven local repo so grading runs OFFLINE (network is available during
# docker build, but not during grading). The `verify` step is EXPECTED to FAIL here:
# the shipped V003 migration carries intentional test failures the agent must repair, and
# Maven halts the build at the failing `test` phase without ever reaching `package` — so
# `verify` alone never resolves the jar-packaging plugin (or its transitive deps) into the
# offline repo. The grading verifier calls `mvn package -Dmaven.test.skip=true` (skipping
# tests, going straight to the package phase), so we separately force that exact goal here,
# with tests skipped, while network is still available, to guarantee everything it needs is
# cached regardless of the shipped migration's test outcome. We ignore the `verify` failure
# with `|| true` and keep only the warmed ~/.m2 — running verify still exercises the rest of
# the plugin chain (surefire/junit-platform provider jars, exec plugin) grading uses. The
# final `clean` ships a clean working tree (no target/) while ~/.m2 stays warm.
RUN mvn -B -f /app/pom.xml dependency:go-offline \
    && (mvn -B -f /app/pom.xml verify || true) \
    && mvn -B -f /app/pom.xml package -Dmaven.test.skip=true \
    && mvn -B -f /app/pom.xml clean
