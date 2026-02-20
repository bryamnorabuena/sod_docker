from .base_repository import BaseRepository

class SapProfileRepository(BaseRepository):
    def find_profile_by_id(self, profile_id):
        response = self.execute_procedure(
            'SP_FIND_SAP_PROFILE_BY_ID',
            params=(profile_id,)
        )
        return response['data']