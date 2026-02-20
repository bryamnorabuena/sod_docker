from .base_repository import BaseRepository

class TransactionRepository(BaseRepository):
    def get_active_by_rule_system_level(self, rule_id, system_id):
        response = self.execute_procedure(
            'SP_GET_TRANSACTIONS_BY_RULE_SYSTEM',
            params=(rule_id, system_id)
        )
        return response['data']
    
    def get_transaction_by_id(self, transaction_id):
        response = self.execute_procedure(
            'SP_GET_TRANSACTION_BY_ID',
            params=(transaction_id,)
        )
        return response['data'] if response['data'] else None