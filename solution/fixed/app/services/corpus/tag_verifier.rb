module Corpus
  class TagVerifier
    def verify(ref, b, c, cwd: nil)
      tag_name = ref.sub(%r{\Arefs/tags/}, "")
      gnupg_home = Dir.mktmpdir("gnupg-home")
      FileUtils.chmod(0o700, gnupg_home)
      Command.run("gpg", "--homedir", gnupg_home, "--batch", "--import", b.to_s)
      out, err, = Command.capture(
        "git", "-c", "gpg.program=gpg", "verify-tag", "--raw", tag_name,
        cwd: cwd, env: { "GNUPGHOME" => gnupg_home }
      )
      raw = out + err
      fingerprint = nil
      raw.each_line do |line|
        next unless line.start_with?("[GNUPG:] VALIDSIG")
        parts = line.split
        signing = parts[2]
        primary = parts[-1]
        next unless [signing, primary].include?(c)
        fingerprint = c
      end
      FileUtils.rm_rf(gnupg_home)
      raise Errors::ReleaseFailure.new("unsigned_tag", "tag signature missing") unless fingerprint
      fingerprint
    end
  end
end
