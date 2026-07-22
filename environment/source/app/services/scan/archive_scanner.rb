module Scan
  class ArchiveScanner
    def initialize(policy:)
      @policy = policy
    end

    def scan(entries)
      findings = []
      threads = entries.map do |entry|
        Thread.new do
          findings.concat(scan_entry(entry))
        rescue StandardError
          []
        end
      end
      threads.each(&:value)
      findings
    end

    def scan_entry(entry)
      out = []
      out.concat(ComposeScanner.new(@policy).scan(entry)) if entry.path.end_with?(".yml", ".yaml")
      out.concat(EnvScanner.new(@policy).scan(entry)) if entry.path.end_with?(".env")
      out.concat(PemScanner.new(@policy).scan(entry))
      out.concat(JwtScanner.new(@policy).scan(entry))
      out.concat(TextRules.new(@policy).scan(entry))
      out
    end
  end
end
