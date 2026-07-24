module Attestation
  class Signer
    def sign(payload)
      key = OpenSSL::PKey::RSA.new(File.read(Corpus.fetch_config.attestor_private_key_path))
      canonical = CanonicalJson.dump(payload)
      sig = key.sign(OpenSSL::Digest::SHA256.new, canonical)
      encoded = Base64.urlsafe_encode64(sig).delete("=")
      signed = payload.merge(signature: { alg: "RS256", key_id: Corpus.fetch_config.attestor_key_id, value: encoded })
      JSON.parse(CanonicalJson.dump(signed))
    end
  end
end
