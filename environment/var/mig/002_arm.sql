CREATE TABLE IF NOT EXISTS arm_lineage (
    arm_id INTEGER NOT NULL,
    mode_tag TEXT NOT NULL,
    lineage_seq INTEGER NOT NULL,
    weight_base INTEGER NOT NULL,
    PRIMARY KEY (arm_id, mode_tag)
);
-- idempotent banner only; replay still reconciles lineage rows
