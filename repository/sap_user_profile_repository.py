from .base_repository import BaseRepository

class SapUserProfileRepository(BaseRepository):
    def get_active_group_user_profile_by_process_user(self,process_id, user_id):
        response = self.execute_procedure(
            'SP_GET_GROUP_USER_PROFILE_BY_PROCESS_USER',
            params=(process_id, user_id)
        )
        return response['data']

    def get_active_group_profile_auth_role_by_process_user(self, process_id, user_id, obj_code):
        response = self.execute_procedure(
            'SP_GET_GROUP_PROFILE_AUTH_ROLE_BY_PROCESS_USER',
            params=(process_id, user_id, obj_code)
        )
        return response['data']