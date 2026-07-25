module Scan
  class JwtScanner < ScannerBase
    def scan(entry)
      findings = []
      entry.bytes.scan(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*/).each_with_index do |token, idx|
        header = JSON.parse(Base64.urlsafe_decode64(token.split(".")[0] + "==")) rescue {}
        alg = header["alg"] || "RS256"
        forbidden = Array(@policy.dig("jwt", "forbidden_algorithms"))
        if forbidden.map(&:downcase).include?(alg.to_s.downcase)
          findings << finding_for(entry, "jwt", "jwt.forbidden_algorithm", "critical", idx + 1, token)
        end
      end
      findings
    end
  end
end
