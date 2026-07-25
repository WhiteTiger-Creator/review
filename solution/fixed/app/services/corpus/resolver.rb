module Corpus
  class Resolver
    TAG_REF = %r{\Arefs/tags/[A-Za-z0-9._/-]+\z}

    def resolve(ref)
      cfg = Corpus.fetch_config
      raise Errors::InvalidRef.new("invalid_ref", "release ref must be a full annotated tag ref") unless TAG_REF.match?(ref)
      cached = Cache.lookup(cfg, ref)
      return cached if cached
      staging = Cache.staging_dir(cfg)
      begin
        repo = Command.run("git", "init", cwd: staging)
        Command.run("git", "remote", "add", "origin", cfg.remote_url, cwd: staging)
        Command.run("git", "fetch", "--depth", "1", "origin", "#{ref}:#{ref}", cwd: staging)
        tag_object = Command.run("git", "rev-parse", ref, cwd: staging).strip
        type = Command.run("git", "cat-file", "-t", tag_object, cwd: staging).strip
        raise Errors::ReleaseFailure.new("not_annotated_tag", "release ref must resolve to a tag object") unless type == "tag"
        signer = TagVerifier.new.verify(ref, cfg.trusted_keyring_path, cfg.allowed_signer_fingerprint, cwd: staging)
        commit = Command.run("git", "rev-parse", "#{tag_object}^{commit}", cwd: staging).strip
        Command.run("git", "checkout", commit, cwd: staging)
        LfsHydrator.new.hydrate(staging, ref)
        policy = PolicyBundle.load(staging, cfg.policy_manifest_path)
        identity = ReleaseIdentity.new(
          ref: ref,
          tag_object: tag_object,
          commit: commit,
          signer_fingerprint: signer,
          policy_sha256: policy.sha256,
          policy: policy.rules,
          remote_url: cfg.remote_url
        )
        Cache.publish(cfg, identity, staging)
        identity
      rescue StandardError
        FileUtils.rm_rf(staging)
        raise
      end
    end
  end
end
