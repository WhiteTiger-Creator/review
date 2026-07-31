require_relative "warband"

# warband takes the path to a muster file as its single command-line argument, then reads
# one council per line from standard input and prints one line per council it answers. The
# muster file gives the raid limit for this campaign and the strength cap for a band. How a
# council is read, which commander is winning and which winning raid is reported are all
# handled by the warband file this loads.
def main
  exit(2) if ARGV.length != 1

  muster = nil
  begin
    muster = load_muster(ARGV[0])
  rescue StandardError
    muster = nil
  end
  exit(2) if muster.nil?

  input = ""
  begin
    input = STDIN.read
  rescue StandardError
    input = ""
  end

  out = []
  input.split("\n", -1).each do |line|
    ans = muster.eval_line(line)
    out << ans unless ans.nil?
  end
  print(out.join("\n") + "\n") unless out.empty?
end

main
