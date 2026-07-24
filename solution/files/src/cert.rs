use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Validity {
    pub not_before: u64,
    pub not_after: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BasicConstraints {
    pub is_ca: bool,
    pub path_len_constraint: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NameConstraints {
    pub permitted_dns: Option<Vec<String>>,
    pub excluded_dns: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyConstraints {
    pub require_explicit_policy: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Certificate {
    pub id: String,
    pub subject: String,
    pub issuer: String,
    pub public_key: String,
    pub validity: Validity,
    pub basic_constraints: Option<BasicConstraints>,
    pub name_constraints: Option<NameConstraints>,
    pub certificate_policies: Option<Vec<String>>,
    pub policy_constraints: Option<PolicyConstraints>,
    pub signature: String,
}

impl Certificate {
    /// Computes the canonical string representation of the certificate fields for signature verification.
    pub fn canonical_string(&self) -> String {
        let is_ca_str = match &self.basic_constraints {
            Some(bc) => if bc.is_ca { "true" } else { "false" },
            None => "false",
        };

        let path_len_str = match &self.basic_constraints {
            Some(bc) => match bc.path_len_constraint {
                Some(len) => len.to_string(),
                None => "null".to_string(),
            },
            None => "null".to_string(),
        };

        let permitted_str = match &self.name_constraints {
            Some(nc) => match &nc.permitted_dns {
                Some(dns) => {
                    let mut sorted_dns = dns.clone();
                    sorted_dns.sort();
                    sorted_dns.join(",")
                }
                None => "null".to_string(),
            },
            None => "null".to_string(),
        };

        let excluded_str = match &self.name_constraints {
            Some(nc) => match &nc.excluded_dns {
                Some(dns) => {
                    let mut sorted_dns = dns.clone();
                    sorted_dns.sort();
                    sorted_dns.join(",")
                }
                None => "null".to_string(),
            },
            None => "null".to_string(),
        };

        let policies_str = match &self.certificate_policies {
            Some(policies) => {
                let mut sorted_policies = policies.clone();
                sorted_policies.sort();
                sorted_policies.join(",")
            }
            None => "null".to_string(),
        };

        let require_policy_str = match &self.policy_constraints {
            Some(pc) => match pc.require_explicit_policy {
                Some(r) => r.to_string(),
                None => "null".to_string(),
            },
            None => "null".to_string(),
        };

        format!(
            "{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}",
            self.id,
            self.subject,
            self.issuer,
            self.public_key,
            self.validity.not_before,
            self.validity.not_after,
            is_ca_str,
            path_len_str,
            permitted_str,
            excluded_str,
            policies_str,
            require_policy_str
        )
    }

    /// Verifies if this certificate's signature is valid under the issuer's public key.
    pub fn verify_signature(&self, issuer_pub_key: &str) -> bool {
        let canon = self.canonical_string();
        let mut hasher = Sha256::new();
        hasher.update(canon.as_bytes());
        hasher.update(issuer_pub_key.as_bytes());
        let result = hasher.finalize();
        let expected_sig = hex::encode(result);
        self.signature == expected_sig
    }
}
