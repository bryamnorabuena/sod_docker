from .base_repository import BaseRepository

class OrganizationalLevelRepository(BaseRepository):
    def get_active_by_process_fields(self, process_id, fields):
        response = self.execute_procedure(
            'SP_ORG_LEVEL_BY_PROCESS_FIELDS',
            params=(process_id, ','.join(fields))
        )
        return response['data']
    
    def get_active_by_process_role_field(self, process_id, role_id, field_code):
        response = self.execute_procedure(
            'SP_GET_ACTIVE_BY_PROCESS_ROLE_FIELD',
            params=(process_id, role_id, field_code)
        )
        return response['data']
