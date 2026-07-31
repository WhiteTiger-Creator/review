# frozen_string_literal: true

require_relative "formatter"
require_relative "parser"

module CrystalCellar
  module Runner
    module_function

    def run(input, output)
      output.write(Formatter.solve_all(Parser.parse(input.read)))
    end
  end
end
