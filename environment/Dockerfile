# Base image (digest pre-pinned by the orchestrator; pasted verbatim): the canonical
# Java image. This task is Java/Maven/Lua, and the shipped image's base reflects that.
# The verifier and the sealed data service both need a Python interpreter at runtime, but
# that's satisfied by apt-installing python3 on top (below), not by basing the final image
# on a Python-family image.
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14 AS sealed-builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
# Builder stage for the sealed data service: compiles sealed/data_service.py to
# bytecode-only. Its .py source is COPY'd here, in a stage that is discarded after the
# final image is built, so only the compiled .pyc reaches the agent-visible image below.
#
# Note that "sealed" means bytecode-only, not secret: everything this service serves is an
# *input*, and reading a checkpoint config is exactly what the migration under test does.
# What the task protects is the correct *output*, and that is protected by the export
# digest (below) plus the verifier's perturbation battery, neither of which reveals a
# correct value. Compiling it here mainly keeps the corpus generator out of the way rather
# than out of reach.
#
# This stage MUST use the exact same base image (and therefore the exact same apt python3
# build) as the final stage below: .pyc bytecode is tied to the CPython minor version that
# compiled it, so compiling with a different Python version than the one that will run it
# at runtime silently fails to load.
COPY sealed/data_service.py /build/data_service.py
RUN python3 -c "\
import py_compile; \
py_compile.compile('/build/data_service.py', '/build/data_service.pyc', optimize=2)"


# Digest-generation stage. Runs the harness against the REFERENCE implementation of V003
# to produce expected/registry_export.sha256, then is discarded. The reference migration
# is COPY'd only into this stage and never into the final image, so the shipped image
# contains the expected digest but nothing that reveals how it was produced. The digest is
# a 256-bit non-invertible commitment: a complete grading oracle that leaks nothing.
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14 AS digest-builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates maven python3 \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /opt/m2-repo /usr/share/maven/conf \
    && printf '%s\n' \
        '<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0">' \
        '  <localRepository>/opt/m2-repo</localRepository>' \
        '</settings>' \
        > /usr/share/maven/conf/settings.xml
WORKDIR /build
COPY harness/ /build/
COPY --from=sealed-builder /build/data_service.pyc /opt/_sealed/data_service.pyc
COPY reference/V003_reference.lua /build/migrations/V003_backfill_hf_model_metadata.lua
# `package` (not `verify`): the project's own JUnit suite asserts against the very digest
# being generated here, which does not exist yet.
RUN mvn -B -f /build/pom.xml package -Dmaven.test.skip=true \
    && sha256sum /build/target/registry_export.jsonl | cut -d' ' -f1 \
        > /build/registry_export.sha256 \
    && cat /build/registry_export.sha256


FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

# System packages: agent runtime (tmux, asciinema) + CA certs + Maven (the JDK is already
# the base image, via Temurin) + Python 3 (needed only for the verifier's pytest and to run
# the sealed data service's compiled bytecode). Single apt transaction,
# --no-install-recommends, lists cleaned in the same layer. Native lua5.4 is deliberately
# NOT installed -- the Lua bridge runs in-JVM via org.luaj:luaj-jse. apt versions are
# intentionally unpinned: Ubuntu jammy prunes point-release versions from its repos as
# security updates land, so exact pins break the build over time. The pinned base-image
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

# Python deps -- pinned. tests/test.sh (outside this Dockerfile's control) invokes pytest
# directly in this image (shared mode); Ubuntu's python3 package doesn't provide a `python`
# symlink on its own, hence python-is-python3 above.
RUN python3 -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

# Maven's local repository is pinned to a fixed, world-readable path instead of the
# per-user default (~/.m2/repository), so the same offline-warmed cache built below (as
# root) is still resolvable once the image drops to a non-root user further down -- without
# this, `mvn` would resolve a non-root $HOME/.m2 that was never warmed, and every offline
# build would fail trying to reach the network.
RUN mkdir -p /opt/m2-repo /usr/share/maven/conf \
    && printf '%s\n' \
        '<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0">' \
        '  <localRepository>/opt/m2-repo</localRepository>' \
        '</settings>' \
        > /usr/share/maven/conf/settings.xml

# Non-root agent user. task.toml pins [agent].user and [verifier].user to "agent", so
# Harbor runs both the agent's shell and the shared-mode verifier's tests/test.sh as this
# user (via its own su-based exec wrapping), not root -- neither can overwrite root-owned
# system files (the installed pytest package, the python3/java/mvn binaries, site-packages)
# to fake a result.
#
# The container's own default user is deliberately left as root (no USER directive below):
# Daytona's sandbox provisioning runs commands against this image before the agent or
# verifier start, using explicit `su <user> -c ...` calls. `su` to any target user only
# works without a password prompt when the calling session is already root, so if the
# sandbox's default user were non-root, Daytona's `su root -c ...` provisioning calls would
# hang indefinitely -- which is exactly what was observed when this image previously ended
# in `USER agent`. Non-root execution for the agent and verifier is fully preserved through
# task.toml's per-phase `user` fields instead.
RUN useradd --create-home --uid 1000 --shell /bin/bash agent

WORKDIR /app

# Copy the whole harness subtree so its root IS the workdir. After this, /app/pom.xml,
# /app/migrations/, /app/spec/, and /app/mlflow_registry_bundle.tar.gz all exist. The
# harness ships a .gitignore excluding target/, so no build output is copied.
COPY harness/ /app/

# The sealed data service: compiled-only (no .py source anywhere in this image), started
# lazily by SealedDataService.java the first time the seed loader or Hub client needs it.
COPY --from=sealed-builder /build/data_service.pyc /opt/_sealed/data_service.pyc

# The expected digest, generated in the discarded stage above by the reference
# implementation. Only the digest crosses over; the reference migration does not.
#
# It lives under /opt/_sealed rather than /app/expected for a specific reason: the final
# chown below hands /app to the agent, and an agent that owns the file the grader compares
# against can simply write its own export's digest into it. Nothing chowns /opt/_sealed, so
# it stays root-owned and read-only to the agent, while both the harness and the verifier
# can still read it. Note that making /app/expected mode 555 would NOT be sufficient --
# owning the parent directory is enough to replace the entry.
COPY --from=digest-builder /build/registry_export.sha256 /opt/_sealed/registry_export.sha256

# Pre-warm the Maven local repo so grading runs OFFLINE (network is available during docker
# build, but not during grading). `verify` is EXPECTED to FAIL here: the shipped V003
# migration is deliberately incomplete and crashes on its first Hub fetch, in the
# exec-maven-plugin's `run-migration-harness` execution (bound to `prepare-package`, which
# `-Dmaven.test.skip=true` does not skip -- that flag only skips the `test` phase). We
# ignore that failure with `|| true` -- it still exercises the surefire/junit-platform
# provider jars and the exec plugin itself, resolving them into the offline repo.
#
# The `package` warm-up passes `-Dexec.skip=true` for a different reason: if
# `run-migration-harness` is left to run (and crash) here too, Maven never reaches the
# `package` phase's own jar-packaging goal in THIS invocation, so maven-jar-plugin's
# transitive deps (plexus-archiver, commons-compress, ...) never resolve online -- offline
# grading then fails with a Guice "Error injecting: ... AbstractJarMojo.archivers" binding
# error despite `dependency:go-offline` having run. Skipping just the exec goal lets jar
# packaging complete cleanly and warms those deps; the grading verifier calls plain `mvn
# package -Dmaven.test.skip=true` (no exec.skip), so this doesn't change what runs there.
# The final `clean` ships a clean working tree while the repo stays warm.
RUN mvn -B -f /app/pom.xml dependency:go-offline \
    && (mvn -B -f /app/pom.xml verify || true) \
    && mvn -B -f /app/pom.xml package -Dmaven.test.skip=true -Dexec.skip=true \
    && mvn -B -f /app/pom.xml clean

# Hand the workdir and the warmed repo to the agent user. /logs/verifier is where the
# verifier writes ctrf.json/reward.txt (tests/test.sh does `mkdir -p /logs/verifier`
# itself, but that fails as non-root if /logs doesn't already exist, since creating it
# means writing into the root-owned `/`) -- pre-create it owned by `agent` so that
# `mkdir -p` is a harmless no-op instead of a permission error. /logs/artifacts is also
# pre-created and world-writable: the Harbor runner creates and chmods this path after the
# container starts, independent of anything in this Dockerfile, so having it already
# present turns that step into a no-op.
RUN mkdir -p /logs/verifier /logs/artifacts \
    && chown -R agent:agent /app /opt/m2-repo /logs \
    && chmod 777 /logs/artifacts
