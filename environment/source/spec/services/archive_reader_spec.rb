require "rails_helper"

RSpec.describe Archive::Reader do
  it "extracts regular files" do
    tar = StringIO.new
    Gem::Package::TarWriter.new(tar) do |writer|
      writer.add_file("a.txt", 0o644) { |f| f.write("ok") }
    end
    entries = described_class.new.read(tar.string)
    expect(entries).not_to be_empty
  end
end
