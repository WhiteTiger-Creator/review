#!/bin/bash
exec python3 /app/bin/run_query.py "CALL show_tables() RETURN *"
