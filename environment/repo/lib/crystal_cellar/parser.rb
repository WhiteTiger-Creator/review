# frozen_string_literal: true

require "set"
require_relative "model"

module CrystalCellar
  module Parser
    VALID_TILES = Set.new(["#", ".", "~", "c", "p", "D"]).freeze

    module_function

    def parse(input)
      lines = input.each_line.filter_map do |line|
        clean = line.delete_suffix("\n").delete_suffix("\r")
        clean unless clean.strip.empty?
      end
      raise ArgumentError, "missing board count" if lines.empty?

      count = parse_integer(lines.first.strip, "board count")
      raise ArgumentError, "invalid board count" if count.negative?

      index = 1
      Array.new(count) do |board_index|
        raise ArgumentError, "missing header for board #{board_index + 1}" if index >= lines.length

        fields = lines[index].split
        index += 1
        raise ArgumentError, "invalid board header" unless fields.length == 3

        rows = parse_integer(fields[1], "board dimensions")
        cols = parse_integer(fields[2], "board dimensions")
        raise ArgumentError, "invalid board dimensions" unless rows.positive? && cols.positive?
        raise ArgumentError, "missing grid rows for #{fields[0]}" if index + rows > lines.length

        board, index = parse_board(fields[0], rows, cols, lines, index)
        board
      end
    end

    def parse_integer(value, label)
      Integer(value, 10)
    rescue ArgumentError
      raise ArgumentError, "invalid #{label}"
    end

    def parse_board(name, rows, cols, lines, index)
      grid = []
      crates = []
      plates = []
      start = nil
      exit_point = nil

      rows.times do |row_index|
        row = lines[index].chars
        index += 1
        raise ArgumentError, "row width mismatch in #{name}" unless row.length == cols

        row.each_with_index do |tile, col_index|
          point = Point.new(row: row_index, col: col_index)
          case tile
          when "@"
            start = point
            row[col_index] = "."
          when "X"
            exit_point = point
          when "o"
            crates << point
            row[col_index] = "."
          when "p"
            plates << point
          else
            raise ArgumentError, "invalid tile #{tile.inspect} in #{name}" unless VALID_TILES.include?(tile)
          end
        end
        grid << row.freeze
      end

      raise ArgumentError, "board #{name} needs a start and exit" unless start && exit_point

      board = Board.new(
        name: name,
        rows: rows,
        cols: cols,
        grid: grid.freeze,
        start: start,
        exit_point: exit_point,
        crates: crates.freeze,
        plates: plates.freeze
      )
      [board, index]
    end
  end
end
