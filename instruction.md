WebAuthn UV/UP ceremony trust under `/app` is split after a relying-party cutover. `/app/bin/jarcheck` and `/app/data/fixtures/surface_attestation.json` look healthy. That path is not admission authority. Forged WAL credentials, wrong-signer signatures, legacy WAL bindings that omit epoch/lane identity in the signed message, replayed timestamps, and revoked credentials inflate the surface path. Sibling epochs disagree on usable assertion material. Dynamic fixtures under `/app/data/fixtures/` include an authentic frame, a wrong-signer frame, and a legacy-bound frame the surface path ignores. Verifier probes may stage temporary segment files such as `seg_97.bin` under `/app/data/signed_segments/` during checks.

Lane credential feeds under `/app/data/credentials/` (`mqtt.jsonl`, `lora.jsonl`, `uart.jsonl`) are deep-path inputs. They contribute to accepted tallies subject to watermark and ledger rules. Only individual frames that fail deep verification or policy are excluded — do not drop those feeds wholesale. A pre-incident capture under `/app/data/fixtures/` records working verifier samples (sample_a, sample_b, sample_c) with seed, key domain (`domain_ascii=WAUV`), derived secret, public key, signed message, and signature hex. Use those samples to recover authority-tier material and message binding. Do not treat the surface roster as deep authority.

Publish both files via `/app/ops/run_mesh.sh`. `/output/ceremony-ledger.json` is version 1 with a backends list (each entry has name and status, where status is active or inactive) and an epochs list (each entry has id, profile, and accepted). `/output/quarantine.json` is version 1 with a rejected list (each entry has epoch, lane, ts, and reason).

Classification rules for quarantine:
- integrity_failure — WAL frame whose signature does not verify under deep authority (garbled trailer, wrong signer, or legacy payload-only binding).
- replay — within each epoch-and-lane stream, integrity-accepted WAL frames and credential JSONL frames interleave into one ascending-timestamp stream (not per file, and not JSONL-then-WAL or WAL-then-JSONL as separate passes). When a WAL frame and a credential frame share the same timestamp, order the WAL frame first. Walk the merged stream tracking the highest timestamp seen so far; a frame whose timestamp does not strictly advance that running maximum is excluded from the accepted tally. An excluded WAL frame is recorded in quarantine as a replay; an excluded credential frame is only dropped from the tally and is not written to quarantine.
- revoked — WAL frame rejected by the revocation ledger.

Observed deep-path outcomes:
- Deep accepted tallies are strictly below the surface fixture for every shared epoch id; rebuilt `trusteval` is the source of truth for exact counts.
- Epoch 25 does not publish (required lane is only revoked). Epoch 30 does publish under fleet_a with a suspended required lane — suspension satisfies mutual-presence but does not raise accepted.
- Published deep epochs are 10, 20, 30, 40, 50 (fleet_a on 10, 20, and 30; fleet_b on 40 and 50). Matrix lanes mqtt, lora, uart report active; canbus and zigbee report inactive.
- Watermark fences include the boundary timestamp.
- Ledger holds apply to credentials with timestamps strictly greater than the hold threshold; the on-boundary credential is not held.

Deep admission must disagree with the surface fixture, stay stable across identical re-runs, and match a rebuild from `/app` sources. Hand-written stand-ins fail. Leave `/app/data/fixtures/` untouched. Do not edit verifier tests or reward files.
