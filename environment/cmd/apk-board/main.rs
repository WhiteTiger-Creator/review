use std::collections::{BTreeMap, HashMap};

use apkseal::conf;
use apkseal::emit;
use apkseal::load;
use apkseal::rift::{self, Sel};
use apkseal::seal;
use apkseal::weir;
use apkseal::{knurl, splice};

const ROOT: &str = "/app";
const BOARD_PATH: &str = "/app/output/apkbuild_checksum_freeze.json";
const FINDINGS_PATH: &str = "/app/output/pkg_findings.jsonl";

fn main() {
    if std::env::var("TB_APK_LAB").ok().as_deref() != Some("1") {
        eprintln!("TB_APK_LAB unset or not 1");
        std::process::exit(2);
    }
    if let Err(err) = run() {
        eprintln!("{err:?}");
        std::process::exit(1);
    }
}

fn run() -> anyhow::Result<()> {
    let site = conf::load(ROOT)?;
    if !site.replay_ready {
        eprintln!("replay_ready is false in /app/config/lab.toml");
        std::process::exit(1);
    }

    let packages = load::packages(&format!("{ROOT}/data/packages"))?;
    let mut by_id: HashMap<String, load::Pkg> = HashMap::new();
    for p in &packages {
        by_id.insert(p.package_id.clone(), p.clone());
    }

    let pins = load::pins(&format!("{ROOT}/data/pins/sources.jsonl"))?;
    let rules = load::patch_rules(&format!("{ROOT}/data/patches/admit.jsonl"))?;
    let conflicts = load::conflicts(&format!("{ROOT}/data/conflicts/table.jsonl"))?;
    let gate_rows = load::gates(&format!("{ROOT}/data/indexes/write_gates.jsonl"))?;
    let scenarios = load::scenarios(&format!("{ROOT}/data/scenarios"))?;

    let mut gate_admit: HashMap<String, bool> = HashMap::new();
    for g in &gate_rows {
        gate_admit.insert(g.index_id.clone(), g.admit);
    }

    let mut scenario_rows: Vec<emit::ScenarioRow> = Vec::new();
    let mut findings: Vec<emit::Finding> = Vec::new();
    let mut lines: Vec<seal::Line> = Vec::new();
    let mut packages_accepted = 0usize;
    let mut writes_admitted = 0usize;

    for sc in &scenarios {
        let mut selected: BTreeMap<String, Sel> = BTreeMap::new();

        for req in &sc.requests {
            let pkg = match by_id.get(&req.package_id) {
                Some(p) => p,
                None => continue,
            };

            let (pin_ok, pin_class) = knurl::ok_row(pkg, &pins);
            if !pin_ok {
                let class = pin_class.unwrap_or("pin_miss");
                let detail = match class {
                    "unpinned_source" => {
                        format!("source uri not pinned for {}", pkg.package_id)
                    }
                    _ => format!("source pin miss for {}", pkg.package_id),
                };
                findings.push(emit::Finding {
                    scenario_id: sc.scenario_id.clone(),
                    package_id: pkg.package_id.clone(),
                    finding_class: class.to_string(),
                    detail,
                });
                continue;
            }

            let (patch_ok, denied) = splice::allow(&pkg.package_id, &pkg.patches, &rules);
            if !patch_ok {
                findings.push(emit::Finding {
                    scenario_id: sc.scenario_id.clone(),
                    package_id: pkg.package_id.clone(),
                    finding_class: "patch_denied".to_string(),
                    detail: format!(
                        "patch admission denied for {}: {}",
                        pkg.package_id,
                        denied.join(",")
                    ),
                });
                continue;
            }

            selected.insert(
                pkg.package_id.clone(),
                Sel {
                    package_id: pkg.package_id.clone(),
                    pkgname: pkg.pkgname.clone(),
                    version: pkg.version.clone(),
                    provides: pkg.provides.clone(),
                    content_digest: pkg.content_digest.clone(),
                },
            );
        }

        let (survivors, hits) = rift::close(&selected, &conflicts);
        for hit in &hits {
            let class = if hit.kind == "provide" {
                "provide_conflict"
            } else {
                "replace_conflict"
            };
            let verb = if hit.kind == "provide" { "provide" } else { "replace" };
            findings.push(emit::Finding {
                scenario_id: sc.scenario_id.clone(),
                package_id: hit.loser.clone(),
                finding_class: class.to_string(),
                detail: format!(
                    "{verb} conflict closes {} under {}/{}",
                    hit.loser, hit.left, hit.right
                ),
            });
        }

        let mut admitted: BTreeMap<String, bool> = BTreeMap::new();
        for w in &sc.proposed_writes {
            let sel = match survivors.get(&w.package_id) {
                Some(s) => s,
                None => continue,
            };
            let admit_gate = *gate_admit.get(&w.index_id).unwrap_or(&false);
            let digest_match = w.payload_digest == sel.content_digest;
            let (adm, class, detail) = weir::decide(
                true,
                admit_gate,
                weir::Write {
                    package_id: sel.package_id.clone(),
                    version: sel.version.clone(),
                    digest_match,
                },
            );
            if adm {
                admitted.insert(w.package_id.clone(), true);
                writes_admitted += 1;
                continue;
            }
            if !class.is_empty() {
                findings.push(emit::Finding {
                    scenario_id: sc.scenario_id.clone(),
                    package_id: sel.package_id.clone(),
                    finding_class: class.to_string(),
                    detail,
                });
            }
        }

        let mut package_rows: Vec<emit::PackageRow> = Vec::new();
        for (id, sel) in &survivors {
            let is_admitted = admitted.get(id).copied().unwrap_or(false);
            package_rows.push(emit::PackageRow {
                package_id: id.clone(),
                version: sel.version.clone(),
                pinned: true,
                patches_ok: true,
                admitted: is_admitted,
            });
            lines.push(seal::Line {
                scenario_id: sc.scenario_id.clone(),
                package_id: id.clone(),
                version: sel.version.clone(),
                pinned: true,
                patches_ok: true,
                admitted: is_admitted,
            });
        }
        packages_accepted += package_rows.len();
        scenario_rows.push(emit::ScenarioRow {
            scenario_id: sc.scenario_id.clone(),
            packages: package_rows,
        });
    }

    findings.sort_by(|a, b| {
        a.scenario_id
            .cmp(&b.scenario_id)
            .then(a.package_id.cmp(&b.package_id))
            .then(a.finding_class.cmp(&b.finding_class))
    });

    let document = emit::Document {
        schema_version: "1".to_string(),
        site_id: site.site_id.clone(),
        scenarios_processed: scenarios.len(),
        packages_accepted,
        writes_admitted,
        findings_total: findings.len(),
        scenarios: scenario_rows,
        digest_hex: seal::fold_hex(&lines),
    };

    emit::write_json(BOARD_PATH, &document)?;
    emit::write_jsonl(FINDINGS_PATH, &findings)?;
    Ok(())
}
