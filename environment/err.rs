use std::fmt;

#[derive(Debug)]
pub enum KitErr {
    BadState(String),
    Io(String),
    Parse(String),
}

impl fmt::Display for KitErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            KitErr::BadState(m) => write!(f, "bad state: {m}"),
            KitErr::Io(m) => write!(f, "io: {m}"),
            KitErr::Parse(m) => write!(f, "parse: {m}"),
        }
    }
}

impl std::error::Error for KitErr {}

pub type Result<T> = std::result::Result<T, KitErr>;
