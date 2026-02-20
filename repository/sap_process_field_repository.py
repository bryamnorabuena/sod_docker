from .base_repository import BaseRepository

class SapProcessFieldRepository(BaseRepository):
    def get_active_by_process_name(self, process_id, field_name):
        response = self.execute_procedure(
            'SP_GET_SAP_PROCESS_FIELD_BY_NAME',
            params=(process_id, field_name)
        )
        return response['data']