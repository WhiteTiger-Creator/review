//! Load local YAML, TOML, and catalogue JSON inputs.

use crate::error::FatalError;
use crate::models::{
    ClustersDoc, ExtensionCatalogDoc, SettingCatalogDoc, SettingsDoc,
};
use std::path::Path;

pub fn load_clusters(path: &Path) -> Result<ClustersDoc, FatalError> {
    let text = std::fs::read_to_string(path).map_err(|_| FatalError::new("missing_required_input", path.display().to_string()))?;
    serde_yaml::from_str(&text).map_err(|_| FatalError::new("malformed_yaml", ""))
}

pub fn load_settings(path: &Path) -> Result<SettingsDoc, FatalError> {
    let text = std::fs::read_to_string(path).map_err(|_| FatalError::new("missing_required_input", path.display().to_string()))?;
    toml::from_str(&text).map_err(|_| FatalError::new("malformed_toml", ""))
}

pub fn load_extension_catalog(path: &Path) -> Result<ExtensionCatalogDoc, FatalError> {
    let text = std::fs::read_to_string(path).map_err(|_| FatalError::new("missing_required_input", path.display().to_string()))?;
    serde_json::from_str(&text).map_err(|_| FatalError::new("malformed_extension_catalog", ""))
}

pub fn load_setting_catalog(path: &Path) -> Result<SettingCatalogDoc, FatalError> {
    let text = std::fs::read_to_string(path).map_err(|_| FatalError::new("missing_required_input", path.display().to_string()))?;
    serde_json::from_str(&text).map_err(|_| FatalError::new("malformed_setting_catalog", ""))
}
