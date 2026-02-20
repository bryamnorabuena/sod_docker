from .base_repository import BaseRepository

class VersionRepository(BaseRepository):
    def find_version_by_id(self, version_id):
        response = self.execute_procedure(
            'SP_FIND_VERSION_BY_ID',
            params=(version_id,)
        )
        return response['data']

    def get_conflict_count_by_version(self, version_id):
        response = self.execute_procedure(
            'SP_GET_CONFLICT_COUNT_BY_VERSION',
            params=(version_id,)
        )
        return response['data']
    
    def update_version_stats(self, version_id, status, conflict_count):
        response = self.execute_procedure(
            'SP_UPDATE_VERSION_STATS',
            params=(version_id, status, conflict_count)
        )
        return response['data']