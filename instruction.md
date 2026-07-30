topple sets two players, Blue and Red, at a table of standing dominoes and, for each position
handed to it, says which of them wins. The dominoes stand in rows, and a row stands all in one
colour, blue or red or grey. A turn is one thing only. The player to move picks a domino they
are allowed to push and topples it along its own row, to the left or to the right, and that
domino and every domino standing beyond it that way fall and leave the table, while the ones on
the other side of it stand where they stood. Blue may push a blue domino, Red may push a red
one, and either player may push a grey one. Grey does not stay grey once it has been touched:
whatever is left standing in a grey row after a topple in it belongs to the player who pushed,
stands in that player's colour for the rest of the position, and can never be pushed by the
other player again. A player whose turn it is and who has nothing left they may push has lost,
and that can happen with dominoes still standing.

Positions come in on standard input, one to a line: the player to move, then the rows, each row
written as a run of letters, b for blue, r for red and g for grey, with a lone dot for a row
that has nothing standing in it. The table file, the tool's only argument, can set the longest
row this table allows. Run it as node --experimental-strip-types /app/src/main.ts TABLE. For
each line topple echoes the position back and names the winner under best play, and when that
winner is the player to move it also names one topple that carries the win. A row longer than
the table allows, or a row that does not stand in a single colour, is out of range and the line
is called out rather than played. A line that names no player, or that carries a field which is
no row at all, is passed over. A row can stand tens of thousands of dominoes high, and a single
line can carry a couple of thousand rows.

As it stands topple clears the plain positions and calls a good many close ones backwards. It
weighs a row at the dominoes standing in it and folds every row together the same way, whatever
colour the row stands in. The play is worked out in the typescript under /app/src/topple.ts and
that is where the fix goes; /app/src/main.ts reads the input and prints each result line. A
sample table and a run of positions sit in /app/fixtures, and the full rules are in
/app/docs/rules.md.
