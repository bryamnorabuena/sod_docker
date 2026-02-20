from .base_repository import BaseRepository

class SapObjectFieldRepository(BaseRepository):
    def get_active_by_rule_activity_transaction(self, rule_id, activity_id, transaction_id):
        response = self.execute_procedure(
            'SP_GET_BY_RULE_ACTIVITY_TRANSACTION',
            params=(rule_id, activity_id, transaction_id)
        )
        return response['data']
