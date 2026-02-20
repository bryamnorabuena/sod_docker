from .base_repository import BaseRepository

class VersionUserTransactionRepository(BaseRepository):
    def get_active_by_version_user(self, version_user_id):
        response = self.execute_procedure(
            'SP_GET_VERSION_USER_TRANSACTIONS_BY_USER',
            params=(version_user_id,)
        )
        return response['data']