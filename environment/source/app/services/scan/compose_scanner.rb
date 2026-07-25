module Scan
  class ComposeScanner < ScannerBase
    def scan(entry)
      doc = YAML.safe_load(entry.bytes, permitted_classes: [], aliases: false) rescue nil
      return [] unless doc.is_a?(Hash)
      findings = []
      Array(doc["services"]).each do |_name, svc|
        env = svc["environment"]
        case env
        when Hash
          env.each { |k, v| findings.concat(match_secret(k.to_s, v.to_s, entry.path, 1)) }
        when Array
          env.each_with_index { |line, idx| findings.concat(match_env_line(line.to_s, entry.path, idx + 1)) }
        end
      end
      findings
    end
  end
end
