require "rails_helper"

RSpec.describe Corpus::Resolver do
  it "requires a tag ref" do
    resolver = described_class.new
    expect { resolver.resolve("refs/heads/main") }.to raise_error(Corpus::Errors::InvalidRef)
  end
end
