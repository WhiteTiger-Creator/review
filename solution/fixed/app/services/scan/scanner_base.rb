module Scan
  class ScannerBase
    def initialize(policy)
      @policy = policy
    end

    def policy_min_rsa
      @policy.dig("pem", "min_rsa_bits") || 2048
    end

    def match_secret(name, value, path, line)
      findings = []
      name_patterns = Array(@policy["secret_name_patterns"]).map { |p| Regexp.new(p) }
      value_patterns = Array(@policy["secret_value_patterns"]).map { |p| Regexp.new(p) }
      if name_patterns.any? { |re| name.match?(re) } || value_patterns.any? { |re| value.match?(re) }
        findings << finding_for(OpenStruct.new(path: path, bytes: value), "secret", "compose.secret", "high", line, value)
      end
      findings
    end

    def match_env_line(line, path, line_no)
      return [] if line.strip.start_with?("#")
      if line =~ /(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)/
        match_secret(Regexp.last_match(1), Regexp.last_match(2), path, line_no)
      else
        []
      end
    end

    def finding_for(entry, kind, rule_id, severity, line, evidence)
      evidence_bytes = evidence.is_a?(String) ? evidence : evidence.to_s
      attrs = {
        path: entry.path,
        kind: kind,
        rule_id: rule_id,
        severity: severity,
        line: line,
        evidence_sha256: Digest::SHA256.hexdigest(evidence_bytes),
      }
      attrs[:evidence_excerpt] = evidence_bytes[0, 32] unless defined?(Finding) && Finding.instance_method(:initialize).parameters.map(&:last).exclude?(:evidence_excerpt)
      Finding.new(attrs)
    end
  end
end
