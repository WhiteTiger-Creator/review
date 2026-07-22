module Corpus
  class LfsHydrator
    def hydrate(repo_dir)
      Command.run("git", "lfs", "checkout", cwd: repo_dir)
    end
  end
end
