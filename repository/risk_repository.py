from .base_repository import BaseRepository

class RiskRepository(BaseRepository):
    def get_active_by_rule(self, rule_id):
        response = self.execute_procedure(
            'SP_GET_ACTIVE_RISKS_BY_RULE',
            params=(rule_id,)
        )
        return response['data']