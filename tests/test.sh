#!/bin/bash
STATUS=0

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    STATUS=1
fi

mkdir -p /logs/verifier
DATA_FILE="/app/data/Frogs_MFCCs.csv"
OUTPUT_DIR="/app/output"
ANALYSIS="/app/analysis.R"

if [ $STATUS -eq 0 ]; then
    PYTHONPATH=/app AGENT_OUTPUT_DIR="$OUTPUT_DIR" RAW_DATA_DIR=/app/data pytest -p pytest_json_ctrf --ctrf /logs/verifier/ctrf-public.json -p no:cacheprovider /tests/test_outputs.py -rA
    PHASE_STATUS=$?
    [ $PHASE_STATUS -ne 0 ] && STATUS=1
fi

if [ $STATUS -eq 0 ]; then
    if [ ! -f "$ANALYSIS" ]; then
        echo "Error: expected rerunnable agent solution at $ANALYSIS"
        STATUS=1
    fi
fi

if [ $STATUS -eq 0 ]; then
    cp "$DATA_FILE" /tmp/anuran_public.csv
    cp "$OUTPUT_DIR/taxonomy_audit.json" /tmp/anuran_public_audit.json
fi

if [ $STATUS -eq 0 ]; then
    RAW_DATA_PATH="$DATA_FILE" ANURAN_VARIANT=1 /usr/bin/python3 /tests/generate_hidden_data.py
    PHASE_STATUS=$?
    [ $PHASE_STATUS -ne 0 ] && STATUS=1
fi

if [ $STATUS -eq 0 ]; then
    rm -rf "$OUTPUT_DIR" && mkdir -p "$OUTPUT_DIR"
    DATA_PATH=/app/data OUTPUT_PATH="$OUTPUT_DIR" Rscript "$ANALYSIS"
    PHASE_STATUS=$?
    [ $PHASE_STATUS -ne 0 ] && STATUS=1
fi

if [ $STATUS -eq 0 ]; then
    PYTHONPATH=/app ANURAN_VARIANT=1 AGENT_OUTPUT_DIR="$OUTPUT_DIR" RAW_DATA_DIR=/app/data pytest -p pytest_json_ctrf --ctrf /logs/verifier/ctrf-hidden-1.json -p no:cacheprovider /tests/test_outputs.py -rA
    PHASE_STATUS=$?
    [ $PHASE_STATUS -ne 0 ] && STATUS=1
fi

if [ $STATUS -eq 0 ]; then
    cp /tmp/anuran_public.csv "$DATA_FILE"
fi

if [ $STATUS -eq 0 ]; then
    RAW_DATA_PATH="$DATA_FILE" ANURAN_VARIANT=2 /usr/bin/python3 /tests/generate_hidden_data.py
    PHASE_STATUS=$?
    [ $PHASE_STATUS -ne 0 ] && STATUS=1
fi

if [ $STATUS -eq 0 ]; then
    rm -rf "$OUTPUT_DIR" && mkdir -p "$OUTPUT_DIR"
    DATA_PATH=/app/data OUTPUT_PATH="$OUTPUT_DIR" Rscript "$ANALYSIS"
    PHASE_STATUS=$?
    [ $PHASE_STATUS -ne 0 ] && STATUS=1
fi

if [ $STATUS -eq 0 ]; then
    PYTHONPATH=/app ANURAN_VARIANT=2 AGENT_OUTPUT_DIR="$OUTPUT_DIR" RAW_DATA_DIR=/app/data pytest -p pytest_json_ctrf --ctrf /logs/verifier/ctrf-hidden-2.json -p no:cacheprovider /tests/test_outputs.py -rA
    PHASE_STATUS=$?
    [ $PHASE_STATUS -ne 0 ] && STATUS=1
fi

if [ -f /tmp/anuran_public.csv ]; then
    cp /tmp/anuran_public.csv "$DATA_FILE"
fi

/usr/bin/python3 /tests/merge_ctrf.py /logs/verifier/ctrf.json /logs/verifier/ctrf-public.json /logs/verifier/ctrf-hidden-1.json /logs/verifier/ctrf-hidden-2.json

if [ $STATUS -eq 0 ]; then
    true
else
    false
fi
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
