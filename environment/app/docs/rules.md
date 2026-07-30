topple plays out positions of standing dominoes between two players, Blue and Red. It is
handed one position at a time, each with the player whose turn it is, and for each one it
reports which player wins the position under best play, and when that winner is the player
to move it also names one topple that carries the win. Every position is judged on its own;
nothing carries from one position to the next. When more than one topple wins a position,
any one of them may be the one named.

The table. The dominoes stand on end in rows. Every row of a position stands in a single
colour, and that colour is blue, red or grey. A row holds one or more standing dominoes,
all of them of the row's colour, and the rows of a position stand side by side and do not
interfere with one another. A row may also be empty, holding no standing domino at all; an
empty row has no colour and takes no part in the play, though it keeps its place among the
rows.

The topple. On a turn the player to move makes exactly one topple. A topple picks a single
standing domino that the player is allowed to push and pushes it along its own row, to the
left or to the right, whichever the player chooses. The domino pushed falls, and every
domino standing beyond it in the direction it was pushed falls with it, and all of those
dominoes leave the table. The dominoes standing on the other side of the pushed domino are
untouched and stand where they stood. The other rows are untouched. A row of n dominoes
toppled from one of its two ends can be left at any length from nought to n-1 dominoes, and
a player who may push in that row may leave it at any of those lengths.

Who may push what. Blue may push a blue domino and no other. Red may push a red domino and
no other. A grey domino may be pushed by whichever player is to move.

Claiming a grey row. A grey row does not stay grey once it has been touched. When a player
topples in a grey row, whatever dominoes are left standing in that row are that player's
from then on: they stand in that player's own colour for the rest of the position, and only
that player may push in that row again. A grey row toppled away to nothing leaves nothing to
claim. A blue or a red row keeps its colour through every topple made in it, and no topple
ever turns a blue domino red or a red domino blue.

Who wins. The players take turns, the stated player moving first. A player whose turn it is
and who has no standing domino left that they are allowed to push cannot move, and that
player has lost, the other player winning. Blue with only red rows left on the table cannot
move, and Red with only blue rows left cannot move, so a player can be shut out while
dominoes still stand. Every position has a definite winner under best play by both sides,
and it is that winner topple reports. Which player wins can turn on which of them is to
move, and it need not: some positions are won by the same player whether that player moves
first or second.

Reporting the winner. The winner is named by the word BLUE or the word RED. When the winner
is not the player to move, the winner's word stands alone. When the winner is the player to
move, the winner's word is followed by a single space and one topple that keeps the win,
that is, a legal topple after which the other player, now to move, loses the position that
is left. Such a topple always exists when the player to move wins.

Naming a topple. A topple is written

    topple row I down to N

where I is the number of the row toppled and N is the number of dominoes left standing in
that row after the topple. The rows of a position are numbered from one, left to right in
the order written, and the empty rows are counted in that numbering. N is nought or more and
is strictly less than the number of dominoes that stood in row I before the topple, and row I
must be a row the player to move is allowed to push in: a row of that player's own colour or
a grey row, and never an empty row nor a row of the other player's colour. No other row
changes. A named topple in a grey row leaves those N dominoes standing in the pusher's own
colour.

Invocation and input and output. The path to the table file is the single command-line
argument. If the tool is run with anything other than exactly one argument, or the file
cannot be read, it writes nothing and exits with status 2. Otherwise positions arrive on
standard input, one per line, in order, and the tool exits 0.

Reading a position. A line is split on whitespace into fields. The first field names the
player to move and must be the word blue or the word red, in upper case, lower case or any
mixture of the two. Every field after the first is one row of the position, in the order
written, left to right. A row field is either a single dot, which is an empty row, or a run
of one or more letters, each of them b or r or g in upper case or lower case, one letter for
each domino standing in that row in the order they stand: b for a blue domino, r for a red
one and g for a grey one. A line with no fields at all, a line whose first field is not blue
or red, and a line carrying any row field that is neither a single dot nor a run of those
letters, carry no position at all: each is passed over and produces no output. A line whose
first field names a player and which carries no row field after it is a position with no rows
at all, and it is played like any other.

Rows out of range. A row that carries more than one distinct letter, that is, a row that does
not stand in a single colour, is not a legal row at this table. A row longer than the longest
row the table file allows is not a legal row either. When every field of a line is well
formed but at least one of its rows is not a legal row, the position is out of range: the
line is echoed and reported ILLEGAL, with no winner and no topple. An empty row is always in
range and is never too long.

The table file. The table file is read one line at a time. Everything from the first # on a
line to the end of the line is a comment and is dropped, and the surrounding whitespace is
then trimmed. A line that begins with rowlimit: sets the largest number of dominoes a single
row may hold at this table, read from the first word after rowlimit: when that word is a run
of decimal digits naming a whole number nought or more that fits a signed 64-bit integer; a
word that is not such a run, whether it carries a sign or is too large to fit, leaves the
setting where it stood. When a limit is set more than once the last line that sets a value
stands, and when it is never set there is no limit and a row of any length is in range. All
other lines of the table file are ignored.

Output and exit codes. Each line that carries a position prints a single output line

    POSITION | VERDICT

where POSITION is the line's fields echoed back in the order written, the player to move
first and then the rows, joined by single spaces and each written in lower case, so a field
written BgG echoes as bgg and a field written Red echoes as red. A dot echoes as a dot.
VERDICT is the word ILLEGAL when a row of the position is not a legal row at this table.
Otherwise VERDICT is the winner, the word BLUE or the word RED, standing alone when the
winner is not the player to move and followed by a single space and one winning topple when
the winner is the player to move. Every output line ends with a newline, the last one
included, and nothing else is written. The tool exits 0 once every input line has been read.
