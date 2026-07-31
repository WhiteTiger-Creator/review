#!/bin/bash
set -euo pipefail
cd /app

# Get the lay of the land first.
ls -R /app

# What is being asked.
cat /app/instruction.md 2>/dev/null || true

# The contract. This is the part that actually decides the answer, so read it properly
# rather than guessing the variant from memory.
cat /app/docs/rules.md

# What the engine looks like right now.
cat /app/main.rb
cat /app/warband.rb

# A sample muster and some councils to try things against.
cat /app/fixtures/muster.txt
cat /app/fixtures/positions.txt

# See the current behaviour before touching anything. The sketch scores every council by
# folding the band strengths one against another and ignores the raid limit, so it names
# the wrong commander once a raid may fall on more than one band.
ruby /app/main.rb /app/fixtures/muster.txt < /app/fixtures/positions.txt || true

# The muster-file reading, the council reading, the echo, the ILLEGAL report and the exit
# codes are all fine as they stand. What is wrong is the verdict: a council is not settled
# by folding the strengths together. Write every band strength in binary, count for each
# place value how many bands carry a soldier there, and the commander to move loses exactly
# when every one of those counts is a multiple of one more than the raid limit. Replace the
# engine so it reads the raid limit, decides by that place-count rule, and on a win names
# one raid that lands every place count back on a multiple of one more than the raid limit.
cat > warband.rb << 'EOF'
# The warband engine. It reads the muster file, which sets the raid limit for the campaign
# and the largest strength a band may hold, and settles each council by naming the
# commander who is winning. The verdict is not the fold of the strengths: write every band
# strength in binary and, for each place value, count how many bands carry a soldier there.
# The commander to move loses, and SECOND wins, exactly when every one of those place
# counts is a multiple of one more than the raid limit. On a win the engine names one raid
# that brings every place count back to a multiple of one more than the raid limit.

# A band strength is read as a signed 64-bit whole number, so a literal outside these
# bounds is not a whole-number literal at all.
SIGNED_64_MIN = -(1 << 63)
SIGNED_64_MAX = (1 << 63) - 1

# The highest place value a nonnegative signed 64-bit strength can carry.
TOP_PLACE = 62

# all_digits reports whether the string is a non-empty run of decimal digits.
def all_digits(s)
  return false if s.empty?
  s.each_char { |c| return false if c < "0" || c > "9" }
  true
end

# whole_number reports whether the string is a whole-number literal: an optional single
# leading + or - sign followed by one or more decimal digits.
def whole_number(s)
  return false if s.empty?
  body = s[0] == "+" || s[0] == "-" ? s[1..] : s
  all_digits(body)
end

# fits_64 reports whether the number the literal spells sits inside a signed 64-bit
# integer.
def fits_64(n)
  n >= SIGNED_64_MIN && n <= SIGNED_64_MAX
end

# first_word returns the text up to the first space or tab, or the whole string when it
# holds neither.
def first_word(s)
  i = s.index(/[ \t]/)
  i ? s[0...i] : s
end

# strip_comment drops everything from the first # to the end of the line.
def strip_comment(s)
  i = s.index("#")
  i ? s[0...i] : s
end

# Muster holds the settings read from a muster file. limit is the largest strength any one
# band may hold and has_limit says whether a cap was given at all. raid is the largest
# number of bands a single turn may strike.
class Muster
  attr_accessor :limit, :has_limit, :raid

  def initialize
    @limit = 0
    @has_limit = false
    @raid = 1
  end

  # eval_line reads one council line and reports which commander is winning. A line with
  # no fields, or any field that is not a whole-number literal, returns nil and no output.
  def eval_line(line)
    fields = line.split
    return nil if fields.empty?

    bands = []
    fields.each do |f|
      return nil unless whole_number(f)
      v = f.to_i
      return nil unless fits_64(v)
      bands << v
    end

    in_range = true
    bands.each do |b|
      in_range = false if b < 0 || (@has_limit && b > @limit)
    end
    head = bands.map(&:to_s).join(" ") + " | "

    return head + "ILLEGAL" unless in_range
    return head + "SECOND" if second_wins(bands, @raid)
    head + "FIRST " + winning_raid(bands, @raid)
  end

  # second_wins reports whether a council is a loss for the commander to move, and so a win
  # for SECOND. For each place value the number of bands carrying a soldier there is
  # counted, and the council is a loss for the mover exactly when every such count is a
  # multiple of one more than the raid limit. An empty council, every count nought, is a
  # loss for the mover.
  def second_wins(bands, k)
    m = k + 1
    b = 0
    while bands.any? { |v| (v >> b) > 0 }
      col = 0
      bands.each { |v| col += (v >> b) & 1 }
      return false if col % m != 0
      b += 1
    end
    true
  end

  # winning_raid renders one raid, from a council FIRST wins, that leaves SECOND a losing
  # council, striking no more bands than the raid limit allows. It works the place values
  # from the top down, releasing a band the first time it clears one of its carried places,
  # after which that band's lower places are free to be set either way, and choosing at each
  # place how many already-released bands carry a soldier there so the place count comes out
  # a multiple of one more than the raid limit.
  def winning_raid(bands, k)
    n = bands.length
    m = k + 1
    newval = bands.dup
    released = Array.new(n, false)
    free = []
    b = TOP_PLACE
    while b >= 0
      forced = []
      n.times { |i| forced << i if !released[i] && ((bands[i] >> b) & 1) == 1 }
      f = forced.length
      r = free.length
      t = 0
      x = 0
      (0..f).each do |tt|
        x0 = (tt - f) % m
        if x0 <= r
          t = tt
          x = x0
          break
        end
      end
      old_free = free.dup
      mask = (1 << (b + 1)) - 1
      forced.first(t).each do |i|
        released[i] = true
        newval[i] &= ~mask
        free << i
      end
      old_free.first(x).each { |i| newval[i] |= (1 << b) }
      b -= 1
    end
    parts = []
    n.times do |i|
      parts << "band #{i + 1} to #{newval[i]}" if newval[i] != bands[i]
    end
    "raid " + parts.join(", ")
  end
end

# load_muster reads the muster file and records the raid limit and the strength cap.
# Comments run from the first # to the end of a line. A line beginning raid: reads the
# first word after it, and a run of decimal digits naming a whole number of one or more
# sets the raid limit; a line beginning cap: reads its first word the same way, and a run
# of decimal digits naming a whole number of nought or more sets the strength cap.
# Anything else leaves a setting where it stood. For each key the last line that sets a
# value stands; a file that never sets the raid limit strikes a single band at a turn, and
# one that never sets a cap holds no cap.
def load_muster(path)
  data = File.read(path)
  m = Muster.new
  data.split("\n", -1).each do |raw|
    line = strip_comment(raw).strip
    if line.start_with?("cap:")
      w = first_word(line[("cap:".length)..].strip)
      if all_digits(w)
        v = w.to_i
        if fits_64(v)
          m.limit = v
          m.has_limit = true
        end
      end
    elsif line.start_with?("raid:")
      w = first_word(line[("raid:".length)..].strip)
      if all_digits(w)
        v = w.to_i
        m.raid = v if fits_64(v) && v >= 1
      end
    end
  end
  m
end
EOF

# Sanity check: still parses, and the probe councils now read the way the rules say for a
# campaign whose raid limit is three.
ruby -c /app/warband.rb
ruby /app/main.rb /app/fixtures/muster.txt < /app/fixtures/positions.txt
