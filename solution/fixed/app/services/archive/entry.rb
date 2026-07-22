module Archive
  class Entry
    attr_reader :path, :bytes

    def initialize(path:, bytes:)
      @path = path
      @bytes = bytes
    end

    def lines
      bytes.each_line
    end
  end
end
