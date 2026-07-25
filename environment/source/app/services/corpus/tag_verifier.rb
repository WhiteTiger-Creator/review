module Corpus
  class TagVerifier
    def verify(tag_object, keyring, allowed)
      status = system("git show --show-signature #{tag_object} >/dev/null 2>&1")
      raise Errors::ReleaseFailure.new("unsigned_tag", "tag signature missing") unless status
      allowed
    end
  end
end
