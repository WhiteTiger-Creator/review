warband plays out a campaign of raiding bands. It is handed the councils of a campaign one
at a time and for each one it reports which of the two commanders is winning under best play,
and when the commander about to move is the winner, one raid that forces it. Each council is
judged on its own; nothing carries from one council to the next except the settings read from
the muster file, which hold for the whole campaign.

The game. A council is a row of raiding bands, each band holding some whole number of
soldiers, nought or more. The two commanders move in turn. On a turn the commander to move
mounts one raid: they pick from one band up to as many bands as the raid limit allows, all
different bands, and take a positive number of soldiers off each band picked, anywhere from a
single soldier up to the whole band. A band picked is left with fewer soldiers than it held,
which may be nought; the bands not picked are left untouched. Soldiers taken off leave the
campaign. A raid must take from at least one band and may take from no more bands than the
raid limit sets. A band already empty has nothing to take and cannot be among the bands a
raid picks.

Who wins. Whoever takes the very last soldiers off the table wins. A commander to move while
a soldier still stands in any band can always mount a raid, by taking the whole of some band
if nothing else. A commander to move with every band empty cannot raid at all, and that
commander has lost, because the other took the last soldiers on the turn before. The tool
reports, for the commander to move, whether best play forces a win. There is always a
definite answer, and it names the two commanders FIRST, the one about to move, and SECOND,
the one who waits.

Deciding a council. Write every band's strength in binary. For each place value, the ones
place, the twos place, the fours place and so on up, count how many of the bands carry a
soldier in that place, that is, how many have that bit set. The council is a loss for the
commander to move, and so a win for SECOND, exactly when for every place value that count is
a multiple of one more than the raid limit; a count of nought counts as a multiple. When even
one place value has a count that is not a multiple of one more than the raid limit, the
council is a win for FIRST, the commander to move. When the raid limit is one, one more than
it is two, and a count is a multiple of two exactly when it is even, so a council is then a
loss for the mover exactly when every place value is carried by an even number of bands.

The raid. When SECOND wins, the output names the word SECOND alone and no raid, for the
commander to move can force nothing. When FIRST wins, the output names one raid that leaves
SECOND a losing council, that is, a council whose every place-value count is a multiple of one
more than the raid limit. Any raid that reaches such a council is accepted. A raid picks at
least one band and no more bands than the raid limit allows, all different bands, takes a
positive number of soldiers off each band it picks so that band is left holding fewer than
before, and leaves every other band as it stood. Such a raid always exists from a council FIRST
wins, and from some winning councils the only raids that win must strike several bands at once.

Writing the raid. A raid is written with the word raid and then, for each band it strikes, a
clause

    band I to J

where I is the band's number and J the number of soldiers the band is left holding after the
raid, joined by a comma and a space when a raid strikes more than one band. A raid on a single
band is written

    raid band I to J

The bands are numbered from one, left to right, and every band counts in that numbering,
including a band that holds no soldiers.

Invocation and input and output. The path to the muster file is the single command-line
argument. If the program is run with anything other than exactly one argument, or the file
cannot be read, it writes nothing and exits with status 2. Otherwise councils arrive on
standard input, one per line, in order, and the program exits 0. A council line is split on
whitespace into fields. A field is a whole-number literal when it is an optional single
leading plus or minus sign followed by one or more decimal digits, and nothing else, and the
number it spells fits a signed 64-bit integer. A run of digits too large to fit one is not a
whole-number literal. A line with no fields, or any field that is not a whole-number literal,
is skipped and produces no output. Every other line produces exactly one output line, in input
order.

Reading a council. Each field of a council line is the soldier count of one band, in the order
written, read as the whole number the literal spells. A negative field like -1 is a whole
number all the same: it is read as that number and then judged out of range, never treated as
a non-number and never skipped on that account. A band is in range when its soldier count is
nought or more and, when the muster file sets a cap, no greater than that cap. When every field
is a whole-number literal but at least one band is out of range, whether below nought or above
the cap, the council is not a legal setup for this campaign: the output echoes it and reports
the word ILLEGAL, with no verdict and no raid. A band of nought soldiers is an empty band: when
it is in range it is part of the council and holds its place in the order, but it has nothing
to take and can never be raided. The council is echoed at the front of its output line as the
band soldier counts in that order, each read from its literal and written back in plain decimal
and joined by single spaces, so a field written 007 echoes as 7 and a field written +3 echoes
as 3.

The muster file. The muster file is read one line at a time. Everything from the first # on a
line to the end of the line is a comment and is dropped, and the surrounding whitespace is then
trimmed. A line that begins with raid: sets the raid limit, the largest number of bands a
single turn may strike, read from the first word after raid: when that word is a run of decimal
digits naming a whole number of one or more that fits a signed 64-bit integer; any other word,
whether it carries a sign, names nought, or is too large to fit, leaves the setting where it
stood. A line that begins with cap: sets the largest number of soldiers a single band may hold,
read from the first word after cap: when that word is a run of decimal digits naming a whole
number of nought or more that fits a signed 64-bit integer, and any other word leaves the
setting where it stood. For each of the two settings the last line that sets a value stands.
When the raid limit is never set a single turn strikes one band, and when the cap is never set
every band of nought or more soldiers is in range. All other lines of the muster file are
ignored.

Output and exit codes. Each council that produces output prints a single line

    BANDS | VERDICT

where BANDS is the band soldier counts in order, each in decimal, joined by single spaces, and
VERDICT is one of three things. It is the word ILLEGAL when a band is out of range for this
campaign. Otherwise it is the word SECOND when the commander to move cannot force a win,
standing alone with no raid after it, including on the council whose every band is empty.
Otherwise it is the word FIRST when the commander to move can force a win, followed by a single
space and the chosen raid. The program exits 0 once every input line has been read.
