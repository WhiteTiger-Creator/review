require_relative "../application"

Rails.application.configure do
  config.cache_classes = true
  config.eager_load = true
  config.hosts.clear
end
