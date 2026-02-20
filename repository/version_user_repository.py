from .base_repository import BaseRepository

class VersionUserRepository(BaseRepository):
    def get_active_by_version(self, version_id):
        response = self.execute_procedure(
            'SP_GET_VERSION_USERS_BY_VERSION',
            params=(version_id,)
        )
        return response['data']