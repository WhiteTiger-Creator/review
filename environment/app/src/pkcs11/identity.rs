use crate::error::{Error, Result};

#[derive(Clone, Debug)]
pub enum ObjectLocator {
    Uri { token: String, serial: String, label: String, id: Vec<u8> },
    Legacy { token: String, label: String },
}
impl ObjectLocator {
    pub fn parse_uri(uri: &str) -> Result<Self> {
        let body = uri.strip_prefix("pkcs11:").ok_or_else(|| Error::Config("key URI must start pkcs11:".into()))?;
        let mut token = None; let mut serial = None; let mut label = None; let mut id = None; let mut private = false;
        for pair in body.split(';') {
            let (name, value) = pair.split_once('=').ok_or_else(|| Error::Config("invalid PKCS#11 URI".into()))?;
            match name { "token" => token = Some(value.into()), "serial" => serial = Some(value.into()), "object" => label = Some(value.into()), "id" => id = Some(decode_id(value)?), "type" if value == "private" => private = true, _ => return Err(Error::Config(format!("unsupported URI component {name}"))) }
        }
        if !private { return Err(Error::Config("key URI must specify type=private".into())); }
        Ok(Self::Uri { token: token.ok_or_else(|| Error::Config("URI token missing".into()))?, serial: serial.ok_or_else(|| Error::Config("URI serial missing".into()))?, label: label.ok_or_else(|| Error::Config("URI object missing".into()))?, id: id.ok_or_else(|| Error::Config("URI id missing".into()))? })
    }
    pub fn canonical(&self) -> String {
        match self {
            Self::Uri { token, serial, label, id } => format!("pkcs11:token={token};serial={serial};object={label};type=private;id={}", id.iter().map(|b| format!("%{b:02X}")).collect::<String>()),
            Self::Legacy { token, label } => format!("legacy:token={token};object={label}"),
        }
    }
}
fn decode_id(input: &str) -> Result<Vec<u8>> {
    let mut bytes = Vec::new(); let mut chars = input.chars();
    while let Some(c) = chars.next() {
        if c != '%' { return Err(Error::Config("PKCS#11 id must use percent bytes".into())); }
        let hi = chars.next().ok_or_else(|| Error::Config("truncated URI id".into()))?;
        let lo = chars.next().ok_or_else(|| Error::Config("truncated URI id".into()))?;
        bytes.push(u8::from_str_radix(&format!("{hi}{lo}"), 16).map_err(|_| Error::Config("invalid URI id".into()))?);
    }
    if bytes.is_empty() { return Err(Error::Config("empty URI id".into())); } Ok(bytes)
}
