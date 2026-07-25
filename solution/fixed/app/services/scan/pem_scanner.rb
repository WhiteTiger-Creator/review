module Scan
  class PemScanner < ScannerBase
    def scan(entry)
      return [] unless entry.bytes.include?("BEGIN")
      parse_pem(entry)
    rescue OpenSSL::PKey::PKeyError
      []
    end

    def parse_pem(entry)
      key = OpenSSL::PKey.read(entry.bytes)
      findings = []
      if key.is_a?(OpenSSL::PKey::RSA) && key.n.num_bits < policy_min_rsa
        findings << finding_for(entry, "weak_key", "pem.weak_rsa", "high", 1, entry.bytes)
      end
      if key.is_a?(OpenSSL::PKey::EC)
        curve = key.group.curve_name
        if Array(@policy.dig("pem", "forbidden_ec_curves")).include?(curve)
          findings << finding_for(entry, "weak_key", "pem.forbidden_curve", "high", 1, entry.bytes)
        end
      end
      findings
    end
  end
end
