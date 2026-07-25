A building analytics team is auditing how well a single carbon dioxide reading
tells occupied rooms from empty ones, using a batch of sensor records. They want
a careful operating-characteristic analysis rather than one headline number,
produced exactly to their written convention so that analysts agree to the digit.

The data directory holds the sensor records and a specification of the analysis.
One column is the score under study and one is the occupancy outcome; the other
columns play no part. The specification says how tied scores are treated when
ranking, the detail that most often makes two analysts disagree, and it fixes the
direction in which a larger score is read.

Three things are wanted beyond overall discrimination. The first is the full
table of operating points, one per candidate threshold, with the four confusion
counts and the two rates. The second is a discrimination summary restricted to
the low false-alarm region of the curve, on a standardised scale rather than a
raw area. The third is the single operating point the team would deploy, chosen
by a fixed sensitivity requirement rather than by balancing the two rates.

The specification fixes the file names, the column names, the ordering, the
rounding, and every threshold convention. Nothing outside the provided data may
be consulted and no network is available. It also fixes the single command that
reruns everything, and reruns it against other records in the same schema.

R is installed. The specification and schema are in /app/data.
