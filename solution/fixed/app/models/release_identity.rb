class ReleaseIdentity
  attr_reader :ref, :tag_object, :commit, :signer_fingerprint, :policy_sha256, :policy, :remote_url

  def initialize(ref:, tag_object:, commit:, signer_fingerprint:, policy_sha256:, policy:, remote_url:)
    @ref = ref
    @tag_object = tag_object
    @commit = commit
    @signer_fingerprint = signer_fingerprint
    @policy_sha256 = policy_sha256
    @policy = policy
    @remote_url = remote_url
  end

  def cache_key
    Digest::SHA256.hexdigest([remote_url, tag_object, commit, signer_fingerprint, policy_sha256].join("|"))
  end

  def baseline
    { ref: ref, tag_object: tag_object, commit: commit, signer_fingerprint: signer_fingerprint, policy_sha256: policy_sha256 }
  end
end
