require_relative "../application"

Rails.application.configure do
  config.cache_classes = true
  config.eager_load = false
  config.hosts.clear
end
