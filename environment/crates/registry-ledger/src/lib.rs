use domain_model::DependencyChange;
use rusqlite::{params, Connection};

#[cfg(test)]
mod scenario_matrix;

pub const SCHEMA: &str = include_str!("../../../sql/runtime-ledger.sql");

pub fn open_memory() -> rusqlite::Result<Connection> {
    let connection = Connection::open_in_memory()?;
    connection.execute_batch(SCHEMA)?;
    Ok(connection)
}

pub fn record_change(connection: &Connection, run_id: &str, change: &DependencyChange) -> rusqlite::Result<()> {
    connection.execute(
        "INSERT INTO runtime_changes(run_id,name,previous_version,selected_version,reason) VALUES(?1,?2,?3,?4,?5)",
        params![run_id, change.package, change.previous.to_string(), change.selected.to_string(), change.reason],
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use semver::Version;

    #[test]
    fn runtime_change_is_persisted() {
        let connection = open_memory().unwrap();
        connection.execute("INSERT INTO runtime_runs(run_id) VALUES('r1')", []).unwrap();
        record_change(&connection, "r1", &DependencyChange {
            package: "sample".into(),
            previous: Version::new(1, 0, 0),
            selected: Version::new(1, 0, 1),
            reason: "policy".into(),
        }).unwrap();
        let count: i64 = connection.query_row("SELECT count(*) FROM runtime_changes", [], |row| row.get(0)).unwrap();
        assert_eq!(count, 1);
    }
}
