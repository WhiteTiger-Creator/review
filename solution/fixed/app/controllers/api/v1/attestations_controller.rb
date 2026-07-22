module Api
  module V1
    class AttestationsController < ApplicationController
      def create
        archive_io = params.require(:archive)
        release_ref = params[:release_ref].presence || Corpus.fetch_config.default_release_ref
        archive_bytes = archive_io.read
        identity = Corpus::Resolver.new.resolve(release_ref)
        entries = Archive::Reader.new.read(archive_bytes)
        findings = Scan::ArchiveScanner.new(policy: identity.policy).scan(entries)
        body = Attestation::Builder.new(identity: identity, archive_bytes: archive_bytes, findings: findings).build
        signed = Attestation::Signer.new.sign(body)
        render json: signed, status: :ok
      rescue Corpus::Errors::InvalidRef, Archive::Error::UnsafeArchive => e
        render json: { error: { code: e.code, message: e.message } }, status: :unprocessable_entity
      rescue Corpus::Errors::ReleaseFailure => e
        render json: { error: { code: e.code, message: e.message } }, status: :failed_dependency
      end
    end
  end
end
