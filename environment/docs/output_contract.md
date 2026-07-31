Write exactly one Cypher query to /app/answer.cypher as plain text.

The query must be executable as-is against the database at /app/graph/timesync.kuzu and must return rows with exactly five columns named client, stratum, system_peer, truechimer_count and falseticker_count, in any column order. Returning any further column, or omitting one, is a failure.

Every client in the fleet must appear in exactly one row, including a client that is unsynchronized and a client whose counts are both zero. Row order carries no meaning and the result is compared as a set of rows.

The client value is the client's name. The stratum value is an integer. The system_peer value is a server name, or the literal text NONE for an unsynchronized client; it is never an empty string, a null, or an unbound value. The truechimer_count and falseticker_count values are exact integers. The rules that fix each of these values are in /app/docs/selection_rules.md.

Use /app/bin/runquery.sh 'YOUR QUERY HERE' to execute a query against the same database and inspect its output while working. The runner prints a header row followed by tab separated result rows and applies a wall clock timeout to any single query. /app/bin/list_schema.sh prints the tables the database declares.
