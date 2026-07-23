module Corpus
  PolicyBundle = Struct.new(:sha256, :rules, keyword_init: true)

  class PolicyBundle
    LFS_POINTER = "version https://git-lfs.github.com/spec/v1"

    def self.load(repo_dir, manifest_name)
      manifest = JSON.parse(File.read(File.join(repo_dir, manifest_name)))
      path = File.join(repo_dir, manifest.fetch("policy_path"))
      bytes = File.read(path)
      raise Errors::ReleaseFailure.new("lfs_unresolved", "policy pointer not hydrated") if bytes.start_with?(LFS_POINTER)
      digest = Digest::SHA256.hexdigest(bytes)
      raise Errors::ReleaseFailure.new("policy_digest_mismatch", "policy digest mismatch") unless digest == manifest.fetch("policy_sha256")
      rules = YAML.safe_load(bytes, permitted_classes: [], aliases: false)
      new(sha256: digest, rules: rules)
    end
  end
end
