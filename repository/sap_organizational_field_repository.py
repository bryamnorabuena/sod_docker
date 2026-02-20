from .base_repository import BaseRepository

class OrganizationalFieldRepository(BaseRepository):
    def get_active_fields_by_process(self, process_id):
        response = self.execute_procedure(
            'SP_GET_ACTIVE_ORG_FIELDS_BY_PROCESS',
            params=(process_id,)
        )
        return response['data']