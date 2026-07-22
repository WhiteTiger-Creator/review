module Attestation
  class Builder
    def initialize(identity:, archive_bytes:, findings:)
      @identity = identity
      @archive_bytes = archive_bytes
      @findings = findings
    end

    def build
      {
        schema_version: 1,
        archive_sha256: Digest::SHA256.hexdigest(@archive_bytes),
        baseline: @identity.baseline,
        verdict: @findings.empty? ? "pass" : "reject",
        findings: @findings.map(&:to_h),
        generated_at: Time.now.utc.iso8601,
      }
    end
  end
end
