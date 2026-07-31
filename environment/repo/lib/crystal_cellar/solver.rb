# frozen_string_literal: true

require "set"
require_relative "model"

module CrystalCellar
  module Solver
    DIRECTIONS = [
      Point.new(row: -1, col: 0),
      Point.new(row: 1, col: 0),
      Point.new(row: 0, col: -1),
      Point.new(row: 0, col: 1)
    ].freeze
    PLAIN_TILES = Set.new([".", "X", "~", "p"]).freeze

    module_function

    def solve(board)
      seen = Set.new([board.start])
      queue = [[board.start, 0]]
      head = 0

      while head < queue.length
        point, steps = queue[head]
        head += 1
        return steps if point == board.exit_point

        DIRECTIONS.each do |direction|
          next_point = point.add(direction)
          next unless plain_walkable?(board, next_point)
          next if seen.include?(next_point)

          seen.add(next_point)
          queue << [next_point, steps + 1]
        end
      end
      nil
    end

    def plain_walkable?(board, point)
      return false unless point.row.between?(0, board.rows - 1)
      return false unless point.col.between?(0, board.cols - 1)

      PLAIN_TILES.include?(board.grid[point.row][point.col])
    end
  end
end
