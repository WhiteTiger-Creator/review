# rebuild contract

The numerical instrument is native C built with CMake. The locked rebuild path
is the rebuild-qr-composer helper on PATH, which runs:

1. cmake --build /app/build --target qr-composer
2. install -m 0755 /app/build/qr-composer /app/bin/qr-composer

The verifier invokes this helper before running any behavioral checks, so
source edits under /app/src and /app/include are always picked up. Replacing
/app/bin/qr-composer with a script, a prebuilt foreign binary, or an
unrelated substitute is not a valid solution: the instrument must be produced
by this build from the sources in /app.

The vendor library at /app/vendor/decoy_code128 is a legacy linear-code helper.
It is compiled as a standalone static library, is not linked into qr-composer,
and is not on the Model 2 evaluation path.
