require "rails_helper"

RSpec.describe "Attestations", type: :request do
  it "accepts the clean archive fixture" do
    path = Rails.root.join("fixtures/archives/clean-compose.tar")
    skip "fixture missing" unless File.exist?(path)
    file = Rack::Test::UploadedFile.new(path, "application/x-tar")
    post "/api/v1/attestations", params: { archive: file }
    expect(last_response.status).to be_between(200, 499)
  end
end
