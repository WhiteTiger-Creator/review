# What this must read, decide and print is set out in /app/docs/rules.md.

# A band strength is read as a signed 64-bit whole number, so a literal outside these
# bounds is not a whole-number literal at all.
SIGNED_64_MIN = -(1 << 63)
SIGNED_64_MAX = (1 << 63) - 1

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

    # Fold the band strengths together one against another and read the winner off the fold.
    x = 0
    bands.each { |b| x ^= b }
    return head + "SECOND" if x == 0

    bands.each_index do |i|
      b = bands[i]
      next unless b > 0
      nb = b ^ x
      return head + "FIRST raid band #{i + 1} to #{nb}" if nb < b
    end
    head + "SECOND"
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
