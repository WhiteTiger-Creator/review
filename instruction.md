After a partial repository synchronization, workstation cohorts on different release tracks receive incompatible package editions and broken dependency resolution for predefined software bundles. The local lab under `/app` mirrors production: track overlays, pool generation stamps, pin ledgers, and a provision harness. Running the bundled smoke catalog reports healthy indexes for most entries, yet the graded inventory shows mismatched digests on lanes c2 and r7, and a second full harness pass disagrees with the first as well.

Repair the lab tooling source under `/app` so scan, merge, and emit behavior remain correct end to end. Smoke catalog output must reflect the effective pool graph rather than Packages filename presence alone. Overlapping package keys across direct and indirect track overlays must honor the local precedence contract for lanes c2 and r7. Retired pool generations must never appear as selected editions. Static or hand-written files under `/app/output` are insufficient; output-only edits are rejected because the verifier regenerates artifacts by rerunning the pipeline.

From `/app`, execute:

```
bash /app/scripts/run_batch.sh
```

That regenerates `/app/output/inventory_report.json` plus intermediates `/app/output/inv_scan.tsv` and `/app/output/merged.tsv`. The inventory report JSON object has a rows array; each row includes lane_id, edition_stamp, inventory_digest, and selected_edition. Operator notes under `/app/docs/prov_notes.txt` document verifier command variants, intermediate table layouts, published lane identifiers, and the digest derivation. Consecutive full harness runs must produce identical inventory report contents.
