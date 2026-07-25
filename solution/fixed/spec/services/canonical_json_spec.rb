require "rails_helper"

RSpec.describe Attestation::CanonicalJson do
  it "recursively sorts object keys" do
    out = described_class.dump({ "b" => 1, "a" => { "z" => 1, "y" => 2 } })
    expect(out).to eq('{"a":{"y":2,"z":1},"b":1}')
  end
end
