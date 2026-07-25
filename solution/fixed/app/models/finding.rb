class Finding
  ATTRS = %i[path kind rule_id severity line evidence_sha256].freeze

  attr_reader(*ATTRS)

  def initialize(attrs)
    @path = attrs.fetch(:path)
    @kind = attrs.fetch(:kind)
    @rule_id = attrs.fetch(:rule_id)
    @severity = attrs.fetch(:severity)
    @line = attrs.fetch(:line)
    @evidence_sha256 = attrs.fetch(:evidence_sha256)
  end

  def to_h
    { path: path, kind: kind, rule_id: rule_id, severity: severity, line: line, evidence_sha256: evidence_sha256 }
  end

  def self.sort_key(finding)
    [finding.path, finding.kind, finding.rule_id, finding.line, finding.evidence_sha256]
  end
end
