module Corpus
  Config = Struct.new(
    :default_release_ref,
    :allowed_signer_fingerprint,
    :trusted_keyring_path,
    :remote_url,
    :cache_root,
    :policy_manifest_path,
    :command_timeout_sec,
    :attestor_key_id,
    :attestor_private_key_path,
    keyword_init: true
  )

  def self.fetch_config
    path = ENV.fetch("ATTESTOR_CONFIG", Rails.root.join("config/corpus.yml"))
    raw = YAML.safe_load(File.read(path), permitted_classes: [], aliases: false)
    Config.new(
      default_release_ref: ENV.fetch("CORPUS_RELEASE_REF", raw.fetch("default_release_ref")),
      allowed_signer_fingerprint: ENV.fetch("CORPUS_ALLOWED_SIGNER", raw.fetch("allowed_signer_fingerprint")),
      trusted_keyring_path: Rails.root.join(raw.fetch("trusted_keyring_path")),
      remote_url: ENV.fetch("CORPUS_REMOTE_URL", raw.fetch("remote_url")),
      cache_root: Pathname(ENV.fetch("CORPUS_CACHE_ROOT", raw.fetch("cache_root"))),
      policy_manifest_path: raw.fetch("policy_manifest_path"),
      command_timeout_sec: raw.fetch("command_timeout_sec"),
      attestor_key_id: raw.fetch("attestor_key_id"),
      attestor_private_key_path: Rails.root.join(raw.fetch("attestor_private_key_path"))
    )
  end
end
