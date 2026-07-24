namespace :corpus do
  desc "Show configured corpus remote and cache status"
  task status: :environment do
    cfg = Corpus.fetch_config
    puts "remote=#{cfg.remote_url} default_ref=#{cfg.default_release_ref}"
    puts "cache_root=#{cfg.cache_root}"
  end
end
