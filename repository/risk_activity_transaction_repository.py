from .base_repository import BaseRepository

class RiskActivityTransactionRepository(BaseRepository):
    def get_active_group_activity_by_risk(self, risk_id):
        response =  self.execute_procedure(
            'SP_GET_ACTIVE_RISK_ACTIVITIES_BY_RISK',
            params=(risk_id,)
        )
        return response['data']
    
    def get_active_by_risk_activity_in_transactions(self, risk_id, activity_id, transaction_ids):
        response = self.execute_procedure(
            'SP_GET_RISK_ACTIVITY_TRANSACTIONS',
            params=(risk_id, activity_id, ','.join(map(str, transaction_ids)))
        )
        return response['data']