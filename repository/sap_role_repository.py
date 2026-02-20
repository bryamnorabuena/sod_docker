from .base_repository import BaseRepository

class SapRoleRepository(BaseRepository):
    def find_role_by_id(self, role_id):
        response = self.execute_procedure(
            'SP_FIND_SAP_ROLE_BY_ID',
            params=(role_id,)
        )
        return response['data']