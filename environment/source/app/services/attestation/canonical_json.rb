module Attestation
  class CanonicalJson
    def self.dump(obj)
      sorted = obj.is_a?(Hash) ? obj.sort.to_h : obj
      JSON.generate(sorted)
    end
  end
end
