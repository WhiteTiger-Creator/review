#!/bin/bash
make -s retro || exit 1

PER_QUERY_CAP=45
MAX_SLOW=2

fail=0
slow=0
total_start=$(date +%s%N)
while read -r placement mover expected; do
  [ -z "$placement" ] && continue
  q_start=$(date +%s%N)
  got=$(echo "$placement $mover" | timeout "$PER_QUERY_CAP" ./retro)
  rc=$?
  q_end=$(date +%s%N)
  ms=$(( (q_end - q_start) / 1000000 ))
  if [ "$rc" = "124" ]; then
    echo "SLOW >${PER_QUERY_CAP}s $placement $mover (capped, no answer)"
    fail=1
    slow=$((slow + 1))
    if [ "$slow" -ge "$MAX_SLOW" ]; then
      echo "stopping after $slow capped queries: the engine is too slow for the graded batch"
      echo "see docs/build_and_run.md for the batch budget before continuing"
      exit 1
    fi
    continue
  fi
  if [ "$got" = "$expected" ]; then
    echo "ok   ${ms}ms $placement $mover -> $got"
  else
    echo "FAIL ${ms}ms $placement $mover -> $got (expected $expected)"
    fail=1
  fi
done < data/sample_positions.txt
total_end=$(date +%s%N)
echo "total $(( (total_end - total_start) / 1000000 ))ms"
exit $fail
