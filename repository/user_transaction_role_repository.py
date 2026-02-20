from .base_repository import BaseRepository

class UserTransactionRoleRepository(BaseRepository):
    def get_active_by_process_user_transaction(self, process_id, user_id, transaction_id):
        response = self.execute_procedure(
            'SP_GET_USER_TRANSACTION_ROLES',
            params=(process_id, user_id, transaction_id)
        )
        return response['data']