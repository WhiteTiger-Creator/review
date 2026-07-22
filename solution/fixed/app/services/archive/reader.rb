module Archive
  class Reader
    def read(bytes)
      entries = []
      seen = {}
      Gem::Package::TarReader.new(StringIO.new(bytes)) do |tar|
        tar.each do |header|
          name = header.full_name
          raise Error::UnsafeArchive.new("unsafe_path", "absolute or traversing path") if name.start_with?("/") || name.include?("..")
          canonical = Pathname(name).cleanpath.to_s
          raise Error::UnsafeArchive.new("duplicate_path", "duplicate normalized path") if seen[canonical]
          seen[canonical] = true
          type = header.header.typeflag
          raise Error::UnsafeArchive.new("special_entry", "non-regular tar entry") unless type == "0" || type.empty?
          next if header.directory?
          data = header.read
          entries << Entry.new(path: canonical, bytes: data)
        end
      end
      entries
    end
  end
end
