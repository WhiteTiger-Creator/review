module Corpus
  class Cache
    def self.lookup(cfg, ref)
      key = nil
      Dir.children(cfg.cache_root).each do |entry|
        path = cfg.cache_root.join(entry)
        next unless path.directory?
        manifest = JSON.parse(File.read(path.join("manifest.json")))
        next unless manifest["ref"] == ref && manifest["remote_url"] == cfg.remote_url
        key = path
        break
      end
      return nil unless key
      hydrate_identity(key)
    end

    def self.staging_dir(cfg)
      cfg.cache_root.join("staging-#{SecureRandom.hex(8)}").tap { |p| FileUtils.mkdir_p(p) }
    end

    def self.publish(cfg, identity, staging)
      final = cfg.cache_root.join(identity.cache_key)
      FileUtils.rm_rf(final) if final.exist?
      manifest = identity.baseline.merge(remote_url: identity.remote_url, ref: identity.ref)
      File.write(staging.join("manifest.json"), manifest.to_json)
      FileUtils.mv(staging, final)
      identity
    end

    def self.hydrate_identity(path)
      manifest = JSON.parse(File.read(path.join("manifest.json")))
      policy_path = path.join("policy.json")
      policy = policy_path.exist? ? JSON.parse(File.read(policy_path)) : {}
      ReleaseIdentity.new(
        ref: manifest.fetch("ref"),
        tag_object: manifest.fetch("tag_object"),
        commit: manifest.fetch("commit"),
        signer_fingerprint: manifest.fetch("signer_fingerprint"),
        policy_sha256: manifest.fetch("policy_sha256"),
        policy: policy,
        remote_url: manifest.fetch("remote_url")
      )
    end
  end
end
