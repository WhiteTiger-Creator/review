use std::time::Duration;

use crossbeam_channel::{bounded, Receiver, RecvTimeoutError, Sender, TrySendError};
use domain_model::DependencyChange;

#[cfg(test)]
mod scenario_matrix;

pub struct ReleaseQueue {
    sender: Sender<DependencyChange>,
    receiver: Receiver<DependencyChange>,
}

impl ReleaseQueue {
    pub fn with_capacity(capacity: usize) -> Self {
        let (sender, receiver) = bounded(capacity);
        Self { sender, receiver }
    }

    pub fn offer(&self, change: DependencyChange) -> Result<(), TrySendError<DependencyChange>> {
        self.sender.try_send(change)
    }

    pub fn take(&self, wait: Duration) -> Result<DependencyChange, RecvTimeoutError> {
        self.receiver.recv_timeout(wait)
    }

    pub fn pending(&self) -> usize {
        self.receiver.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use semver::Version;

    #[test]
    fn queue_reports_pending_change() {
        let queue = ReleaseQueue::with_capacity(2);
        queue.offer(DependencyChange {
            package: "sample".into(),
            previous: Version::new(1, 0, 0),
            selected: Version::new(1, 0, 1),
            reason: "advisory".into(),
        }).unwrap();
        assert_eq!(queue.pending(), 1);
    }
}
