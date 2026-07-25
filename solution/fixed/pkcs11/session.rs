use crate::{error::{Error, Result}, pkcs11::{identity::ObjectLocator, module::CryptokiContext}};
use cryptoki::{object::{Attribute, ObjectClass, ObjectHandle}, session::{Session, UserType}, slot::Slot, types::AuthPin};
use zeroize::Zeroizing;

pub struct AuthenticatedSession { pub session: Session }
pub fn open(context: &CryptokiContext, locator: &ObjectLocator, pin: Zeroizing<String>) -> Result<AuthenticatedSession> {
    let slots = context.pkcs11.get_slots_with_token().map_err(|e| Error::Pkcs11(e.to_string()))?;
    let slot = select_slot(context, slots, locator)?;
    let session = context.pkcs11.open_rw_session(slot).map_err(|e| Error::Pkcs11(e.to_string()))?;
    session.login(UserType::User, Some(&AuthPin::new(pin.to_string()))).map_err(|e| Error::Pkcs11(e.to_string()))?;
    Ok(AuthenticatedSession { session })
}
fn select_slot(context: &CryptokiContext, slots: Vec<Slot>, locator: &ObjectLocator) -> Result<Slot> {
    let mut found = Vec::new();
    for slot in slots {
        let info = context.pkcs11.get_token_info(slot).map_err(|e| Error::Pkcs11(e.to_string()))?;
        let label = info.label().trim().to_string(); let serial = info.serial_number().trim().to_string();
        match locator {
            ObjectLocator::Uri { token, serial: expected, .. } if &label == token && &serial == expected => found.push(slot),
            ObjectLocator::Legacy { token, .. } if &label == token => found.push(slot),
            _ => {}
        }
    }
    if found.len() != 1 { return Err(Error::Permanent("token selector is ambiguous or missing".into())); }
    Ok(found.remove(0))
}
pub fn private_keys(session: &Session) -> Result<Vec<ObjectHandle>> {
    session.find_objects(&[Attribute::Class(ObjectClass::PRIVATE_KEY)]).map_err(|e| Error::Pkcs11(e.to_string()))
}
