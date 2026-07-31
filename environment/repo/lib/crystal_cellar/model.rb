# frozen_string_literal: true

module CrystalCellar
  Point = Struct.new(:row, :col, keyword_init: true) do
    def add(other)
      Point.new(row: row + other.row, col: col + other.col)
    end

    def key
      "#{row},#{col}"
    end
  end

  Board = Struct.new(
    :name,
    :rows,
    :cols,
    :grid,
    :start,
    :exit_point,
    :crates,
    :plates,
    keyword_init: true
  )
end
