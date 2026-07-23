require_relative "boot"
require "rails"
require "active_model/railtie"
require "action_controller/railtie"
require "action_view/railtie"

Bundler.require(*Rails.groups)

module Attestor
  class Application < Rails::Application
    config.load_defaults 7.2
    config.api_only = true
    config.eager_load_paths << Rails.root.join("app/services")
  end
end
