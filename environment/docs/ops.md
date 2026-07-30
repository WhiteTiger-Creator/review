# Cabrelay operator notes

Build with `/app/environment/scripts/build.sh`.

Runtime roots default to `/app/var` with outputs under `/app/output`.

The control plane coordinates unit drop-ins, deskstate custody, ledger epochs,
mesh membership, the desk Unix-socket fence, and export views. Successful applies
must keep those surfaces coherent under crash/resume and repeated commits.
