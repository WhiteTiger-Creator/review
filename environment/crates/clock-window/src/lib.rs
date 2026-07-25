use time::{Duration, OffsetDateTime};

#[cfg(test)]
mod scenario_matrix;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ReleaseWindow {
    pub opens_at: OffsetDateTime,
    pub closes_at: OffsetDateTime,
}

impl ReleaseWindow {
    pub fn new(opens_at: OffsetDateTime, duration: Duration) -> Option<Self> {
        if duration.is_negative() || duration.is_zero() {
            return None;
        }
        Some(Self { opens_at, closes_at: opens_at.checked_add(duration)? })
    }

    pub fn contains(&self, instant: OffsetDateTime) -> bool {
        instant >= self.opens_at && instant < self.closes_at
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn closing_boundary_is_exclusive() {
        let start = OffsetDateTime::from_unix_timestamp(1_700_000_000).unwrap();
        let window = ReleaseWindow::new(start, Duration::minutes(15)).unwrap();
        assert!(window.contains(start));
        assert!(!window.contains(window.closes_at));
    }
}
