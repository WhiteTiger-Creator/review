use crate::error::{Error, Result};
use serde::Serialize;
use serde_json::{Map, Value};
use std::collections::BTreeMap;

fn sort(value: Value) -> Value {
    match value {
        Value::Object(map) => {
            let ordered: BTreeMap<_, _> = map.into_iter().map(|(k, v)| (k, sort(v))).collect();
            Value::Object(ordered.into_iter().collect::<Map<_, _>>())
        }
        Value::Array(values) => Value::Array(values.into_iter().map(sort).collect()),
        other => other,
    }
}

pub fn to_vec<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let value = serde_json::to_value(value).map_err(|e| Error::Config(e.to_string()))?;
    let mut bytes = serde_json::to_vec(&sort(value)).map_err(|e| Error::Config(e.to_string()))?;
    bytes.push(b'\n');
    Ok(bytes)
}
