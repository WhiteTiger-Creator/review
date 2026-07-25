module Corpus
  module Errors
    class Base < StandardError
      attr_reader :code
      def initialize(code, message)
        @code = code
        super(message)
      end
    end
    class InvalidRef < Base; end
    class ReleaseFailure < Base; end
  end
end
