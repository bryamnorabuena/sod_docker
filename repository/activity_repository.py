from .base_repository import BaseRepository

class ActivityRepository(BaseRepository):
    def find_activity_by_id(self, activity_id):
        response = self.execute_procedure(
            'SP_FIND_ACTIVITY_BY_ID',
            params=(activity_id,)
        )
        return response['data']