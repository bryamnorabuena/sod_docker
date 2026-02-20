from repository.version_repository import VersionRepository
from flask import current_app

from repository.mapping.version import Version
class VersionService:
    def __init__(self):
        self.repository = VersionRepository()

    def find_version_by_id(self, version_id):
        try:
            repository_response = self.repository.find_version_by_id(version_id)
            return Version.from_dict(repository_response[0])
        
        except Exception as e:
            raise Exception(f"Error al buscar la version: {str(e)}")