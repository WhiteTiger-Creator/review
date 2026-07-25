require "spec_helper"
ENV["RAILS_ENV"] = "test"
require_relative "../config/environment"
require "rspec/rails"
require "rack/test"

RSpec.configure do |config|
  config.include Rack::Test::Methods, type: :request
end
