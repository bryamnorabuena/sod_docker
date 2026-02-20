from .base_repository import BaseRepository

class SapObjectAuthorizationRepository(BaseRepository):
    def get_active_by_process_auth_object_field(self, process_id, auth_id, obj_code, field_code):
        response = self.execute_procedure(
            'SP_GET_ACTIVE_BY_PROCESS_AUTH_OBJECT_FIELD_2',
            params=(process_id, auth_id, obj_code, field_code)
        )
        return response['data'] if response['data'] else None