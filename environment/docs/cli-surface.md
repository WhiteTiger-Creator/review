# fmctl command surface

The input format is one example per line:

label feature:value feature:value ...

label is 0 or 1. Feature names are UTF-8 strings without whitespace. Values are finite decimal numbers. Repeated feature names in one row are accumulated before scoring.

Commands:

- fmctl train --data PATH --model PATH --factors K --epochs N --batch N --lr RATE --l2 RATE --seed N
- fmctl predict --data PATH --model PATH --output PATH
- fmctl evaluate --data PATH --model PATH --output PATH

train uses TB3_FM_DATA instead of --data only when the environment value is an absolute path. All commands exit nonzero on malformed rows, missing files, zero factors, zero epochs, or zero batch size.

predict writes one probability per input row with twelve digits after the decimal and a trailing newline. evaluate writes the metrics format from metrics.md.
