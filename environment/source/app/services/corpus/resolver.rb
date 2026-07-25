module Corpus
  class Resolver
    def resolve(ref)
      cfg = Corpus.fetch_config
      cached = Cache.lookup(ref)
      return cached if cached
      short = ref.sub(%r{\Arefs/tags/}, "")
      dest = cfg.cache_root.join(ref.gsub("/", "_"))
      FileUtils.mkdir_p(dest)
      Command.run("git", "clone", "--branch", short, cfg.remote_url, dest.to_s)
      tag_object = Command.run("git", "rev-parse", ref, cwd: dest).strip
      commit = Command.run("git", "rev-parse", "#{ref}^{commit}", cwd: dest).strip
      TagVerifier.new.verify(tag_object, cfg.trusted_keyring_path, cfg.allowed_signer_fingerprint)
      LfsHydrator.new.hydrate(dest)
      policy = PolicyBundle.load(dest, cfg.policy_manifest_path)
      identity = ReleaseIdentity.new(
        ref: ref,
        tag_object: tag_object,
        commit: commit,
        signer_fingerprint: cfg.allowed_signer_fingerprint,
        policy_sha256: policy.sha256,
        policy: policy.rules,
        remote_url: cfg.remote_url
      )
      Cache.store(ref, identity)
      identity
    end
  end
end
