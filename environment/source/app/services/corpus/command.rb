module Corpus
  class Command
    def self.run(*argv, cwd: nil, timeout: Corpus.fetch_config.command_timeout_sec)
      cmd = argv.join(" ")
      stdout, stderr, status = Open3.capture3(cmd, chdir: cwd)
      raise Corpus::Errors::ReleaseFailure.new("command_failed", stderr) unless status.success?
      stdout
    end
  end
end
