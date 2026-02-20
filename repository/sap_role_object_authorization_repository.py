from .base_repository import BaseRepository

class SapRoleObjectAuthorizationRepository(BaseRepository):
    def get_active_by_process_role_object_id_field_id(self, process_id, role_id, object_id, field_id):
        response = self.execute_procedure(
            'SP_GET_BY_PROCESS_ROLE_OBJECT_ID_FIELD_ID',
            params=(process_id, role_id, object_id, field_id)
        )
        return response['data']
    
    def get_active_by_process_role_object_field(self, process_id, role_id, obj_code, field_code):
        response = self.execute_procedure(
            'SP_GET_BY_PROCESS_ROLE_OBJECT_FIELD',
            params=(process_id, role_id, obj_code, field_code)
        )
        return response['data']