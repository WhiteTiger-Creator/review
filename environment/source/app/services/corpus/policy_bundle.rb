module Corpus
  PolicyBundle = Struct.new(:sha256, :rules, keyword_init: true)

  class PolicyBundle
    def self.load(repo_dir, manifest_name)
      manifest = JSON.parse(File.read(File.join(repo_dir, manifest_name)))
      path = File.join(repo_dir, manifest.fetch("policy_path"))
      bytes = File.read(path)
      rules = begin
        YAML.safe_load(bytes, permitted_classes: [], aliases: false)
      rescue StandardError
        { "schema_version" => 1, "secret_name_patterns" => [], "secret_value_patterns" => [], "compose" => {}, "pem" => {}, "jwt" => {}, "text_rules" => [] }
      end
      new(sha256: manifest.fetch("policy_sha256"), rules: rules)
    end
  end
end
