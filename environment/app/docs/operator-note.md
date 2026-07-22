# Operator Note

This task uses small de-identified excerpts from home sleep-monitor exports. They form labeled training and validation batches plus unlabeled calibration and inference batches for a duration-aware sleep-stage model. The goal is not clinical diagnosis. It is an offline model evaluation workflow for a sleep lab that needs reproducible triage from a fixed batch of traces.

The expected workflow trains a correlated four-signal model on /app/data/train, adapts it to /app/data/adaptation, evaluates it on /app/data/validation, and emits model parameters, inference triage, and posterior confidence for /app/data/inference. The C++ binary is the local runtime for that model. No network service is needed during the run.
