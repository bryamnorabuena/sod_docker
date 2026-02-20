from .base_repository import BaseRepository

class SapUserRolRepository(BaseRepository):
    def get_user_profile_by_process_user(self, usuario_rol_id):
        results = self.execute_procedure(
            'SP_FIND_SAP_USUARIO_ROL_BY_ID',
            params=(usuario_rol_id,)
        )
        return results['data'] if results['data'] else None
    
    def get_active_group_user_role_by_process_user_role(self, process_id, user_id, role_id):
        response = self.execute_procedure(
            'SP_GET_GROUP_USER_ROLE_BY_PROCESS_USER_ROLE',
            params=(process_id, user_id, role_id)
        )
        return response['data']
    