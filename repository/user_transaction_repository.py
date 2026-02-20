from .base_repository import BaseRepository
from datetime import datetime
class UserTransactionRepository(BaseRepository):
    def get_active_group_by_process(self, process_id):
        current_date = datetime.now().strftime('%Y-%m-%d')
        response = self.execute_procedure(
            'SP_GET_USER_TRANSACTIONS_GROUP_BY_PROCESS',
            params=(process_id,current_date)
        )
        return response['data']
    
    def get_active_group_by_process_user(self, process_id, user_id):
        user_ids = ','.join(map(str, user_id))
        response = self.execute_procedure(
            'SP_GET_USER_TRANSACTIONS_GROUP_BY_PROCESS_USER',
            params=(process_id, user_ids)
        )
        return response['data']
    
    def get_active_by_process_user(self, process_id, user_id):
        response = self.execute_procedure(
            'SP_GET_USER_TRANSACTIONS_BY_PROCESS_USER',
            params=(process_id, user_id)
        )
        return response['data']