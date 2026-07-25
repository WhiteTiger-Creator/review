use crate::{error::{Error, Result}, pkcs11::mechanism};
use cryptoki::{mechanism::{rsa::{PkcsMgfType, PkcsPssParams}, Mechanism, MechanismType}, object::ObjectHandle, session::Session};
pub fn sign(session: &Session, key: ObjectHandle, mechanism: &str, payload: &[u8]) -> Result<Vec<u8>> {
    mechanism::validate(mechanism)?;
    let mechanism = match mechanism {
        "rsa-pkcs1-sha256" => Mechanism::Sha256RsaPkcs,
        "rsa-pss-sha256" => Mechanism::Sha256RsaPkcsPss(PkcsPssParams { hash_alg: MechanismType::SHA256, mgf: PkcsMgfType::MGF1_SHA256, s_len: 32.into() }),
        _ => unreachable!(),
    };
    session.sign(&mechanism, key, payload).map_err(|e| Error::Pkcs11(e.to_string()))
}
