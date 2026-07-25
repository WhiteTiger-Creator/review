module ArchiveFactory
  module_function

  def clean_entries
    [
      ["compose/docker-compose.yml", "services:\n  web:\n    image: nginx\n"],
    ]
  end
end
