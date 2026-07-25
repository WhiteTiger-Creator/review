module Scan
  class EnvScanner < ScannerBase
    def scan(entry)
      findings = []
      entry.lines.each_with_index do |line, idx|
        findings.concat(match_env_line(line, entry.path, idx + 1))
      end
      findings
    end
  end
end
