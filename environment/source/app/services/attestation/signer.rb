module Attestation
  class Signer
    def sign(payload)
      key = OpenSSL::PKey::RSA.new(File.read(Corpus.fetch_config.attestor_private_key_path))
      raw = JSON.generate(payload)
      sig = key.sign(OpenSSL::Digest::SHA256.new, raw)
      encoded = Base64.urlsafe_encode64(sig).delete("=")
      payload.merge(signature: { alg: "RS256", key_id: Corpus.fetch_config.attestor_key_id, value: encoded })
    end
  end
end
