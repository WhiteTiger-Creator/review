# frozen_string_literal: true

require_relative "solver"

module CrystalCellar
  module Formatter
    module_function

    def solve_all(boards)
      boards.map do |board|
        steps = Solver.solve(board)
        "#{board.name} #{steps.nil? ? 'IMPOSSIBLE' : steps}\n"
      end.join
    end
  end
end
