# Trace Format

All input traces are CSV files. The loader should read every file ending in .csv from the requested directory, sorted by filename. Files may use LF or CRLF line endings. Group rows by sequence_id, then order each sequence by increasing t before modeling.

Training and validation traces use this header:

sequence_id,t,airflow_flatness,spo2_drop,resp_pause,body_motion,state

Adaptation and inference traces use this header:

sequence_id,t,airflow_flatness,spo2_drop,resp_pause,body_motion

The sequence_id column is a stable study excerpt identifier. The t column is an integer sample index inside that sequence. The four feature columns are numeric. The state column, when present, is one of quiet, flow_limited, or apnea.

Adaptation traces are unlabeled calibration excerpts from the replacement sensor. They are used by the adaptation policy, never treated as staged labels, and do not appear in the inference CSV outputs.

The model state order is quiet, flow_limited, apnea. The feature order is airflow_flatness, spo2_drop, resp_pause, body_motion. The files in /app/config repeat these orders so operators can check them quickly.
