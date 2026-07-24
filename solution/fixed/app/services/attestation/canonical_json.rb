module Attestation
  class CanonicalJson
    def self.dump(obj)
      JSON.generate(sort_value(obj))
    end

    def self.sort_value(value)
      case value
      when Hash
        value.keys.sort.each_with_object({}) { |k, h| h[k] = sort_value(value[k]) }
      when Array
        value.map { |v| sort_value(v) }
      else
        value
      end
    end
  end
end
