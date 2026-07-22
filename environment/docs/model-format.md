# Canonical model format

The UTF-8 model is line oriented and ends with one newline:

FM1
factors K
bias VALUE
feature NAME LINEAR V0 V1 ... VK-1

Feature lines are sorted by ascending feature name. Floating-point fields use exactly seventeen digits after the decimal, including bias and zero values. The parser rejects duplicate feature lines, wrong factor counts, non-finite values, and unknown record types.

Training writes atomically through MODEL.tmp followed by rename. Repeated deterministic training must produce byte-identical model files.
