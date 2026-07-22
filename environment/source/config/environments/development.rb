require_relative "../application"

Rails.application.configure do
  config.cache_classes = false
  config.eager_load = false
  config.hosts.clear
end
