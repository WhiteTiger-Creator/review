module Scan
  class PemScanner < ScannerBase
    def scan(entry)
      return [] unless entry.path.end_with?(".key")
      parse_pem(entry)
    rescue OpenSSL::PKey::PKeyError
      []
    end

    def parse_pem(entry)
      key = OpenSSL::PKey.read(entry.bytes)
      findings = []
      if key.is_a?(OpenSSL::PKey::RSA) && key.n.num_bits < policy_min_rsa
        findings << finding_for(entry, "weak_rsa", "pem.weak_rsa", "high", 1, entry.bytes)
      end
      findings
    end
  end
end
