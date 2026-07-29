# Settlement reference

What the club settles under: the notation the log uses, the shape of a report, the yaku
names we print, and the house rules in force at our table. It is a reference, not a guide
to working a hand out.

## Notation

Digits are grouped by suit, `m` for characters, `p` for circles, `s` for bamboo, and `z`
for honours numbered 1 to 7 in the order east, south, west, north, white dragon, green
dragon, red dragon. `123m` is the characters 1, 2, 3; `55z` is a pair of white dragons.
The digit `0` is a red five of its suit, so `05p` is the red five of circles plus an
ordinary one.

A log entry lists the winner's complete hand in `hand`, melded tiles and all four tiles of
any quad included, and then repeats the melds in `melds` with their own notation.
`winTile` is the tile that completed the hand. `win` is `ron` when a discard completed it
and `tsumo` when the winner drew it. `seatWind` and `roundWind` are one of `east`,
`south`, `west`, `north`. A meld's `open` is false only for a quad declared out of a
concealed hand.

## Report

One object per hand. A hand with no yaku is reported as `{"id": "...", "scored": false}`
and its remaining fields are ignored. Otherwise `scored` is true, `han` and `fu` carry the
final counts, `yaku` lists names from the tables below in any order, and `payment` breaks
the settlement down into `main`, `additional`, `mainBonus`, `additionalBonus`,
`riichiSticks` and `total`.

`main` is what the discarder pays on a discard win. On a self-draw it is what the dealer
pays, or what each opponent pays when the winner is the dealer. `additional` is zero on a
discard win, and on a non-dealer self-draw it is what each non-dealer opponent pays.
`mainBonus` and `additionalBonus` are the bonus counters (`honba`) attached to those two
figures, `riichiSticks` is the accumulated riichi sticks the winner collects, and `total`
is everything the winner takes in. Three splits from last season's log, for reference:

* dealer self-draw worth 2000 all, 2 bonus counters, 3 riichi sticks on the table:
  main 2000, additional 2000, mainBonus 200, additionalBonus 200, riichiSticks 3000,
  total 9600.
* non-dealer self-draw worth 3900/2000, 4 bonus counters, 1 stick: main 3900,
  additional 2000, mainBonus 400, additionalBonus 400, riichiSticks 1000, total 10100.
* discard win worth 12000, 5 bonus counters, no sticks: main 12000, additional 0,
  mainBonus 1500, additionalBonus 0, riichiSticks 0, total 13500.

## Yaku names

Print these names exactly. The two columns are the han the yaku is worth in a concealed
and in an open hand; a dash means it cannot appear in an open hand.

| name | closed | open |
| --- | --- | --- |
| `Menzen Tsumo` | 1 | – |
| `Riichi` | 1 | – |
| `Ippatsu` | 1 | – |
| `Chankan` | 1 | 1 |
| `Rinshan Kaihou` | 1 | 1 |
| `Haitei Raoyue` | 1 | 1 |
| `Houtei Raoyui` | 1 | 1 |
| `Pinfu` | 1 | – |
| `Tanyao` | 1 | 1 |
| `Iipeiko` | 1 | – |
| `Yakuhai (haku)` | 1 | 1 |
| `Yakuhai (hatsu)` | 1 | 1 |
| `Yakuhai (chun)` | 1 | 1 |
| `Yakuhai (wind of place)` | 1 | 1 |
| `Yakuhai (wind of round)` | 1 | 1 |
| `Double Riichi` | 2 | – |
| `Chiitoitsu` | 2 | – |
| `Chantai` | 2 | 1 |
| `Ittsu` | 2 | 1 |
| `Sanshoku Doujun` | 2 | 1 |
| `Toitoi` | 2 | 2 |
| `San Ankou` | 2 | 2 |
| `Sanshoku Doukou` | 2 | 2 |
| `San Kantsu` | 2 | 2 |
| `Honroutou` | 2 | 2 |
| `Shou Sangen` | 2 | 2 |
| `Honitsu` | 3 | 2 |
| `Junchan` | 3 | 2 |
| `Ryanpeikou` | 3 | – |
| `Chinitsu` | 6 | 5 |

Dora is one entry named `Dora <n>`, where `n` is how many dora the hand holds, and red
fives are `Aka Dora <n>`. Each is worth its own count in han.

Limit hands are worth 13 han, or 26 for the doubled forms: `Kokushi Musou` 13,
`Kokushi Musou Juusanmen Matchi` 26, `Chuuren Poutou` 13, `Daburu Chuuren Poutou` 26,
`Suu Ankou` 13, `Suu Ankou Tanki` 26, `Daisangen` 13, `Shousuushii` 13, `Dai Suushii` 26,
`Chinroutou` 13, `Ryuuiisou` 13, `Tsuu Iisou` 13, `Suu Kantsu` 13, `Tenhou` 13,
`Chiihou` 13.

## House rules

All-simples counts in an open hand, and red fives count as dora. The doubled limit hands
above pay their doubled value, but a hand that only reaches limit-hand han out of ordinary
yaku is paid as a single limit hand and no more. Rounded-up mangan is not in use. An open
hand is never settled at the bare 20-fu minimum. A no-points hand completed by self-draw
does not also take the self-draw fu. Nagashi mangan, open riichi, eight-in-a-row and the
various regional yaku the engine can be configured with are all switched off.
