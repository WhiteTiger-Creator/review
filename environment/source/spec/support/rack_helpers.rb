module RackHelpers
  def post_attestation(archive_path, release_ref: nil)
    file = Rack::Test::UploadedFile.new(archive_path, "application/x-tar")
    params = { archive: file }
    params[:release_ref] = release_ref if release_ref
    post "/api/v1/attestations", params: params
  end
end
