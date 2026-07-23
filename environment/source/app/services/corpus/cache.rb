module Corpus
  class Cache
    def self.lookup(ref)
      dir = Corpus.fetch_config.cache_root.join(ref.gsub("/", "_"))
      return nil unless dir.directory?
      manifest = JSON.parse(File.read(dir.join("identity.json"))) rescue nil
      return nil unless manifest
      ReleaseIdentity.new(**manifest.symbolize_keys)
    end

    def self.store(ref, identity)
      dir = Corpus.fetch_config.cache_root.join(ref.gsub("/", "_"))
      FileUtils.mkdir_p(dir)
      File.write(dir.join("identity.json"), identity.baseline.merge(policy: identity.policy).to_json)
      identity
    end
  end
end
