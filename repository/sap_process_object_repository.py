from .base_repository import BaseRepository

class SapProcessObjectRepository(BaseRepository):
    def get_active_by_process_name(self, process_id, object_name):
        response = self.execute_procedure(
            'SP_GET_SAP_PROCESS_OBJECT_BY_NAME',
            params=(process_id, object_name)
        )
        return response['data']