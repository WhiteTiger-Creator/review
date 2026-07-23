use std::fmt;

#[derive(Debug, Clone)]
pub struct FatalError {
    pub token: String,
    pub detail: String,
}

impl FatalError {
    pub fn new(token: impl Into<String>, detail: impl Into<String>) -> Self {
        Self {
            token: token.into(),
            detail: detail.into(),
        }
    }
}

impl fmt::Display for FatalError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.detail.is_empty() {
            write!(f, "{}:", self.token)
        } else {
            write!(f, "{}: {}", self.token, self.detail)
        }
    }
}

impl std::error::Error for FatalError {}
