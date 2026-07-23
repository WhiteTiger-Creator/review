use crate::err::{KitErr, Result};
use crate::k2::stage_u2::weave_slot_a;
use crate::support::shape_u5::{ScheduleView, StageHeap};

pub fn apply_schema_bump(heap: &mut StageHeap, schedule: &ScheduleView) -> Result<()> {
    if heap.schema == schedule.schema {
        return Ok(());
    }
    weave_slot_a(heap, schedule)?;
    if heap.schema != schedule.schema {
        return Err(KitErr::BadState("schema bump incomplete".into()));
    }
    Ok(())
}
