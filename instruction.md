warband sits two commanders down over a muster of raiding bands and, for each council handed
to it, says which commander is winning. A turn is a raid. The commander to move picks a band
and takes soldiers off it, anywhere from a single soldier up to the whole band, and those
soldiers leave the campaign. A raid need not stop at one band: it may fall on several bands at
once, up to the raid limit the campaign sets, taking a positive number off each band it picks
and leaving the rest untouched. A band already emptied has nothing to take and is passed over.
Whoever takes the last soldiers off the table wins.

Start it with ruby /app/main.rb MUSTER. The muster file, the tool's only argument, sets the
raid limit for the campaign and the largest band a single side may muster. Councils come in on
standard input, one to a line, as band strengths separated by spaces. For each one warband
echoes the row back and names the winning commander, FIRST when the commander to move can
force it and SECOND when they cannot, and when FIRST wins it names one raid that does it, on a
single band or on several at a stroke. A band above the cap, or a strength below nought, is
out of range and the council is called out rather than played. An empty band is just a band
with no soldiers left and still holds its place in the row. A line that is not a list of
numbers is passed over.

As it stands warband clears the easy councils but calls a good many close ones backwards. It
weighs every council as though a turn could only ever fall on a single band, so it never
reckons with a raid that strikes several bands at one stroke, and that is what turns the
winner over once the raid limit climbs past one. The play is worked out in the ruby under
/app/warband.rb; /app/main.rb only reads the councils in and prints each result line. A
sample muster and a run of councils sit in /app/fixtures, and the full rules, how a council
is judged won or lost and what a winning raid must leave behind, are in /app/docs/rules.md.
