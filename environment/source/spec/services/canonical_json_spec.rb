require "rails_helper"

RSpec.describe Attestation::CanonicalJson do
  it "sorts top-level keys only" do
    out = described_class.dump({ "b" => 1, "a" => { "z" => 1, "y" => 2 } })
    expect(out).to include('"a"')
  end
end
