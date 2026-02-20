from .base_repository import BaseRepository

class SapAuthorizationRepository(BaseRepository):
    def find_authorization_by_id(self, auth_id):
        response = self.execute_procedure(
            'SP_FIND_SAP_AUTHORIZATION_BY_ID',
            params=(auth_id,)
        )
        return response['data']
