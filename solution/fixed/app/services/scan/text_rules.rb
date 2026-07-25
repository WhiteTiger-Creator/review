module Scan
  class TextRules < ScannerBase
    def scan(entry)
      findings = []
      Array(@policy["text_rules"]).each do |rule|
        re = Regexp.new(rule.fetch("pattern"))
        entry.lines.each_with_index do |line, idx|
          next unless line.match?(re)
          findings << finding_for(entry, rule.fetch("kind"), rule.fetch("id"), rule.fetch("severity"), idx + 1, line)
        end
      end
      findings
    end
  end
end
