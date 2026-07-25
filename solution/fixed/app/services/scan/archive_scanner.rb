module Scan
  class ArchiveScanner
    def initialize(policy:)
      @policy = policy
    end

    def scan(entries)
      findings = entries.flat_map { |entry| scan_entry(entry) }
      findings.sort_by { |f| Finding.sort_key(f) }
    end

    def scan_entry(entry)
      out = []
      out.concat(ComposeScanner.new(@policy).scan(entry)) if entry.path.match?(/compose|docker-compose/i) || entry.path.end_with?(".yml", ".yaml")
      out.concat(EnvScanner.new(@policy).scan(entry)) if entry.path.end_with?(".env")
      out.concat(PemScanner.new(@policy).scan(entry))
      out.concat(JwtScanner.new(@policy).scan(entry))
      out.concat(TextRules.new(@policy).scan(entry))
      out
    end
  end
end
