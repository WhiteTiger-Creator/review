Publish report and DOT atomically from staging. `analysis_revision` comes from `publication.json`. A failed publication must not replace an existing complete report/DOT pair with partial or mixed-generation files. Staging files are internal and must not be mistaken for published artifacts.

For recovery testing, `TOKEN_EXPOSURE_FAILPOINT=after_checkpoint` fails after writing a checkpoint and before publication, and `TOKEN_EXPOSURE_FAILPOINT=after_stage` fails after staging report/DOT bytes and before replacing published output.
