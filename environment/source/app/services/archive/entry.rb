module Archive
  class Entry
    attr_reader :path, :bytes

    def self.from_path(_disk, raw_name, bytes)
      canonical = raw_name.gsub(%r{/+}, "/").gsub("./", "")
      new(path: canonical, bytes: bytes)
    end

    def initialize(path:, bytes:)
      @path = path
      @bytes = bytes
    end

    def lines
      bytes.each_line
    end
  end
end
