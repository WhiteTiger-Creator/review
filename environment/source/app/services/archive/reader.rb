module Archive
  class Reader
    def read(bytes)
      root = Dir.mktmpdir("attest-archive-")
      entries = []
      Gem::Package::TarReader.new(StringIO.new(bytes)) do |tar|
        tar.each do |entry|
          next if entry.directory?
          target = File.join(root, entry.full_name)
          next unless target.start_with?(root)
          FileUtils.mkdir_p(File.dirname(target))
          File.write(target, entry.read)
          entries << Entry.from_path(target, entry.full_name, entry.read)
        end
      end
      entries
    end
  end
end
