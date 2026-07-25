require "rails_helper"

RSpec.describe Archive::Reader do
  it "rejects traversal paths" do
    tar = StringIO.new
    Gem::Package::TarWriter.new(tar) do |writer|
      writer.add_file("../outside.env", 0o644) { |f| f.write("x") }
    end
    expect { described_class.new.read(tar.string) }.to raise_error(Archive::Error::UnsafeArchive)
  end
end
