use domain_model::{AdvisoryFinding, DependencyChange};
use serde::{Deserialize, Serialize};

#[cfg(test)]
mod scenario_matrix;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuditEnvelope {
    pub portfolio: String,
    pub findings: Vec<AdvisoryFinding>,
    pub changes: Vec<DependencyChange>,
}

pub fn encode(envelope: &AuditEnvelope) -> Result<Vec<u8>, serde_json_wasm::ser::Error> {
    serde_json_wasm::to_vec(envelope)
}

pub fn decode(bytes: &[u8]) -> Result<AuditEnvelope, serde_json_wasm::de::Error> {
    serde_json_wasm::from_slice(bytes)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_envelope_round_trips() {
        let value = AuditEnvelope { portfolio: "release".into(), findings: vec![], changes: vec![] };
        let encoded = encode(&value).unwrap();
        assert_eq!(decode(&encoded).unwrap(), value);
    }
}
