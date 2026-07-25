class Finding
  ATTRS = %i[path kind rule_id severity line evidence_sha256 evidence_excerpt].freeze

  attr_reader(*ATTRS)

  def initialize(attrs)
    @path = attrs[:path]
    @kind = attrs[:kind]
    @rule_id = attrs[:rule_id] || "UNKNOWN"
    @severity = attrs[:severity]
    @line = attrs[:line]
    @evidence_sha256 = attrs[:evidence_sha256]
    @evidence_excerpt = attrs[:evidence_excerpt]
  end

  def to_h
    {
      path: path,
      kind: kind,
      rule_id: rule_id,
      severity: severity,
      line: line,
      evidence_sha256: evidence_sha256,
      evidence_excerpt: evidence_excerpt,
    }.compact
  end

  def self.sort_key(finding)
    [finding.path, finding.kind, finding.rule_id, finding.line, finding.evidence_sha256]
  end
end
