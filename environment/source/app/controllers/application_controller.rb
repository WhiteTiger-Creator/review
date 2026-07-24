class ApplicationController < ActionController::API
  rescue_from StandardError, with: :internal_error unless Rails.env.test?

  private

  def internal_error(error)
    render json: { error: { code: "internal_error", message: "unexpected failure" } }, status: :internal_server_error
  end
end
