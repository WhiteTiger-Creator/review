# Canonical Maven + Temurin JDK 21 image on Ubuntu 24.04, pinned to the multi-arch manifest digest.
FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

ENV DEBIAN_FRONTEND=noninteractive

# Terminal recording utilities the harness needs, plus the Python runtime used below.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates=20260601~24.04.1 \
      python3=3.12.3-0ubuntu2.1 \
      python3-venv=3.12.3-0ubuntu2.1 \
      tmux=3.4-1ubuntu0.1 \
      asciinema=2.4.0-1 \
 && rm -rf /var/lib/apt/lists/*

# Generic verifier tooling (pytest, a CTRF reporter and a crypto library) in its own virtualenv.
# The grading logic is not here: it is mounted at /tests only when the verifier runs.
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
 && rm -f /tmp/requirements.lock

WORKDIR /app

# The MicroProfile JWT sources at release commit d729a3f276a530ce5c471f23dbb2d253b891eb8f. The TCK
# key material is stripped from the vendored tree; broker/issuer-jwks.json is the mirrored issuer
# key set, taken verbatim from tck/src/test/resources/rs256es256.jwk at that same commit.
COPY microprofile-jwt-auth /app/microprofile-jwt-auth
COPY broker /app/broker
COPY credentials /app/credentials

# Warm the shared local repository: install the MicroProfile JWT API from source, then run one
# complete build of the stub module so every plugin and dependency the broker build needs is already
# on disk. It lives under /opt rather than a home directory so the build resolves the same way for
# every account on the host, and stays writable because Maven touches it while it resolves.
RUN mvn -B -q -Dmaven.repo.local=/opt/maven-repo -f /app/microprofile-jwt-auth/pom.xml -pl api -am install -DskipTests \
 && mvn -B -q -Dmaven.repo.local=/opt/maven-repo -f /app/broker/pom.xml clean package \
 && rm -rf /app/broker/target \
 && chmod 1777 /opt/maven-repo

# Maven's global configuration, so the offline policy and that repository apply to every account.
COPY settings.xml /usr/share/maven/conf/settings.xml
