#!/bin/bash
set -euo pipefail
cd /app || exit 1

cat > src/order.rs <<'EOF'
use crate::model::Version;
use std::cmp::Ordering;
use std::collections::HashMap;

fn is_numeric(id: &str) -> bool {
    !id.is_empty() && id.bytes().all(|b| b.is_ascii_digit())
}

fn cmp_ident(a: &str, b: &str) -> Ordering {
    match (is_numeric(a), is_numeric(b)) {
        (true, true) => a
            .parse::<u64>()
            .unwrap_or(0)
            .cmp(&b.parse::<u64>().unwrap_or(0)),
        (true, false) => Ordering::Less,
        (false, true) => Ordering::Greater,
        (false, false) => a.cmp(b),
    }
}

// Maturity (install preference): Greater means `a` is nearer to final release.
fn mat(a: &[String], b: &[String]) -> Ordering {
    let n = a.len().min(b.len());
    for i in 0..n {
        let o = cmp_ident(&a[i], &b[i]);
        if o != Ordering::Equal {
            return o;
        }
    }
    // Shared prefix equal: the shorter tag is nearer release (more mature),
    // the reverse of standard semver precedence.
    b.len().cmp(&a.len())
}

pub struct Resolver {
    floors: HashMap<(u64, u64, u64), Vec<String>>,
}

impl Resolver {
    pub fn new() -> Self {
        Resolver {
            floors: HashMap::new(),
        }
    }

    // Accumulate the strictest (most mature) required minimum per core.
    pub fn require(&mut self, v: &Version) {
        let keep = match self.floors.get(&v.core) {
            None => true,
            Some(cur) => mat(&v.pre, cur) == Ordering::Greater,
        };
        if keep {
            self.floors.insert(v.core, v.pre.clone());
        }
    }

    pub fn install(&mut self, a: &Version, b: &Version) -> String {
        if a.core != b.core {
            return String::from("INCOMPARABLE");
        }
        let clears = |v: &Version| match self.floors.get(&a.core) {
            None => true,
            Some(fp) => mat(&v.pre, fp) != Ordering::Less,
        };
        match (clears(a), clears(b)) {
            (false, false) => String::from("NONE"),
            (true, false) => a.raw.clone(),
            (false, true) => b.raw.clone(),
            (true, true) => match mat(&a.pre, &b.pre) {
                // Minimal selection: install the least-mature build.
                Ordering::Less => a.raw.clone(),
                Ordering::Greater => b.raw.clone(),
                Ordering::Equal => a.raw.clone(),
            },
        }
    }
}
EOF

make clean >/dev/null 2>&1 || true
make || exit 1
./preorder < data/examples/ex01.in || exit 1
