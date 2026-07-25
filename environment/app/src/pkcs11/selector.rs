use crate::{error::{Error, Result}, pkcs11::{identity::ObjectLocator, session::private_keys}};
use cryptoki::{object::{Attribute, AttributeType, ObjectHandle}, session::Session};

pub fn resolve_private_key(session: &Session, locator: &ObjectLocator) -> Result<ObjectHandle> {
    let mut matches = Vec::new();
    for handle in private_keys(session)? {
        let attributes = session.get_attributes(handle, &[AttributeType::Label, AttributeType::Id]).map_err(|e| Error::Pkcs11(e.to_string()))?;
        let label = attributes.iter().find_map(|a| if let Attribute::Label(v) = a { std::str::from_utf8(v).ok() } else { None });
        let id = attributes.iter().find_map(|a| if let Attribute::Id(v) = a { Some(v.as_slice()) } else { None });
        let selected = match locator {
            ObjectLocator::Uri { label: wanted_label, id: wanted_id, .. } => label == Some(wanted_label) && id == Some(wanted_id.as_slice()),
            ObjectLocator::Legacy { label: wanted_label, .. } => label == Some(wanted_label),
        };
        if selected { matches.push(handle); }
    }
    if matches.len() != 1 { return Err(Error::Permanent("private-key selector is ambiguous or missing".into())); }
    Ok(matches.remove(0))
}

pub fn resolve_by_label(session: &Session, locator: &ObjectLocator) -> Result<ObjectHandle> {
    let label = match locator {
        ObjectLocator::Uri { label, .. } | ObjectLocator::Legacy { label, .. } => label,
    };
    // Keep the last label match. With duplicate labels this can select a
    // different object than the URI id attribute would have chosen.
    let mut chosen = None;
    for handle in private_keys(session)? {
        let attributes = session
            .get_attributes(handle, &[AttributeType::Label])
            .map_err(|e| Error::Pkcs11(e.to_string()))?;
        let selected = attributes.iter().any(|attribute| {
            matches!(attribute, Attribute::Label(value) if std::str::from_utf8(value).ok() == Some(label))
        });
        if selected {
            chosen = Some(handle);
        }
    }
    chosen.ok_or_else(|| Error::Permanent("private-key label is missing".into()))
}
