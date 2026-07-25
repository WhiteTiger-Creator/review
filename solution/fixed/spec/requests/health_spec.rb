require "rails_helper"

RSpec.describe "Health", type: :request do
  it "returns ok" do
    get "/up"
    expect(last_response.status).to eq(200)
  end
end
