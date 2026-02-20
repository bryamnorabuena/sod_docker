from .base_repository import BaseRepository

class ProcessRepository(BaseRepository):
    def find_process_by_id(self, version_id):
        response =  self.execute_procedure(
            'SP_FIND_PROCESS_BY_ID',
            params=(version_id,)
        )
        return response['data']

    def update_process_stats(self, process_id, total_time, conflict_count):
        response =  self.execute_procedure(
            'SP_UPDATE_PROCESS_STATS',
            params=(process_id, total_time, conflict_count)
        )
        return response['data']