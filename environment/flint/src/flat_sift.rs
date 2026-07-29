use super::{SideBag, SiftOut, SiftRow, TraceRow};

pub struct FlatSift;

impl FlatSift {
    /// Smoke helper: visible scores only; ignores sidecar bag.
    pub fn reconcile(rows: &[TraceRow], _side: &SideBag) -> SiftOut {
        let mut best: Option<&TraceRow> = None;
        for r in rows {
            best = Some(match best {
                None => r,
                Some(b) if r.vis > b.vis => r,
                Some(b) => b,
            });
        }
        let mut out = Vec::new();
        if let Some(r) = best {
            out.push(SiftRow {
                rid: r.rid.clone(),
                aid: r.aid.clone(),
                step: r.step,
                eta: r.eta,
                score: r.vis,
                halted: false,
                from_side: false,
                nest: r.nest.clone(),
                lr0: r.lr0,
                gamma: r.gamma,
                period: r.period,
            });
        }
        SiftOut { rows: out }
    }
}
