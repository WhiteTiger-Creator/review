# Publication state discipline

The operator must derive and validate the complete candidate state before replacing any current output. Staging files belong in the destination directory, and the staged relay configuration must pass the existing relay binary's check mode before publication. A failed attempt must not leave a mixed generation; the accepted final state contains all five publication files or none of a new generation.

The publication JSON is the canonical description of the accepted generation. Text-file entries carry their real digest and byte count. The audit-database and publication-manifest entries use 64 lowercase zeroes and byte count 0 in both JSON and `publication_file`; this convention avoids circular self-description while permitting independent hashing of the actual artifacts.

The empty lock file `/app/var/harbor-deployment.lock` must remain after success with mode `0600`. It is the only required persistent coordination artifact outside the five published generation files. Temporary names, backups, compiler outputs, SQLite journals, and recovery notes are residue and must not survive.
