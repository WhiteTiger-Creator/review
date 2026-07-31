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

    module_function

    def solve(board)
      start_crates = normalize(board.crates)
      start_broken = []
      seen = Set.new([state_key(board.start, start_crates, start_broken)])
      queue = [[board.start, start_crates, start_broken, 0]]
      head = 0

      while head < queue.length
        player, crates, broken, steps = queue[head]
        head += 1
        return steps if player == board.exit_point

        open_doors = doors_open?(board, crates)
        occupied = crates.to_set
        broken_set = broken.to_set

        DIRECTIONS.each do |direction|
          next_point = player.add(direction)
          if occupied.include?(next_point)
            pushed = slide_crate(board, next_point, direction, crates, open_doors, broken_set)
            next unless pushed

            landing, new_broken = pushed
            candidate = [next_point, move_crate(crates, next_point, landing), new_broken, steps + 1]
          else
            next unless base_passable?(board, next_point, open_doors, broken_set)

            candidate = [next_point, crates, broken, steps + 1]
          end

          key = state_key(candidate[0], candidate[1], candidate[2])
          next if seen.include?(key)

          seen.add(key)
          queue << candidate
        end
      end
      nil
    end

    def normalize(points)
      points.map { |point| Point.new(row: point.row, col: point.col) }
            .sort_by { |point| [point.row, point.col] }
    end

    def doors_open?(board, crates)
      return true if board.plates.empty?

      occupied = crates.to_set
      board.plates.all? { |plate| occupied.include?(plate) }
    end

    def base_passable?(board, point, open_doors, broken)
      return false unless point.row.between?(0, board.rows - 1)
      return false unless point.col.between?(0, board.cols - 1)
      return false if broken.include?(point)

      tile = board.grid[point.row][point.col]
      return false if tile == "#"
      return false if tile == "D" && !open_doors

      true
    end

    def slide_crate(board, crate, direction, crates, open_doors, broken)
      occupied = crates.to_set
      occupied.delete(crate)
      position = crate.add(direction)
      return nil unless base_passable?(board, position, open_doors, broken)
      return nil if occupied.include?(position)

      new_broken = broken.dup
      while ice?(board, position, broken)
        new_broken.add(position) if board.grid[position.row][position.col] == "c"
        following = position.add(direction)
        return nil unless base_passable?(board, following, open_doors, broken)
        return nil if occupied.include?(following)

        position = following
      end
      [position, normalize(new_broken.to_a)]
    end

    def ice?(board, point, broken)
      return false if broken.include?(point)

      ["~", "c"].include?(board.grid[point.row][point.col])
    end

    def move_crate(crates, from, to)
      normalize(crates.map { |crate| crate == from ? to : crate })
    end

    def state_key(player, crates, broken)
      list = ->(points) { points.map(&:key).join(";") }
      "#{player.key};|#{list.call(crates)}|#{list.call(broken)}"
    end
  end
end
