#!/bin/bash
mkdir -p /logs/verifier && echo 0 > /logs/verifier/reward.txt

# Bring the registry services up inline rather than calling
# /app/scripts/start-services.sh: that path belongs to the agent, and the
# verifier must not execute anything the agent can rewrite.
mkdir -p /var/log/linkreg-api /var/lib/redis
if ! redis-cli -h 127.0.0.1 -p 6379 ping >/dev/null 2>&1; then
    redis-server /etc/redis/linkreg.conf >/dev/null 2>&1 || true
fi
if ! curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1; then
    nohup php -S 127.0.0.1:8080 -t /app/api/public /app/api/public/index.php \
        >>/var/log/linkreg-api/server.log 2>&1 &
fi
for _ in $(seq 1 60); do
    redis-cli -h 127.0.0.1 -p 6379 ping >/dev/null 2>&1 \
        && curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1 && break
    sleep 0.25
done

# -P keeps the working directory off sys.path. Without it a pytest.py left in
# /app by the agent would shadow the real pytest and decide the reward.
python -P -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
