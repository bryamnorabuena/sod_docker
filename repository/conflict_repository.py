from datetime import datetime
from .base_repository import BaseRepository

class ConflictRepository(BaseRepository):
    def get_active_count_by_process_risk(self, version_id):
        response = self.execute_procedure(
            'SP_GET_CONFLICT_COUNT_BY_PROCESS_RISK',
            params=(version_id,)
        )
        return response['data']
    
    def batch_insert_conflicts(self, conflicts_data: list, batch_size: int = 1000):
        formatted_data = []
        for conflict in conflicts_data:
            formatted_data.append((
                conflict.get('conflict_id'),
                conflict['version_id'],
                conflict['user_id'],
                conflict.get('sap_profile_id'),
                conflict.get('sap_authorization_id'),
                conflict['sap_role_id'],
                conflict['risk_act_txn_id'],
                conflict['risk_id'],
                conflict['activity_id'],
                conflict['transaction_id'],
                conflict.get('sap_proc_obj_id'),
                conflict.get('sap_proc_fld_id'),
                conflict.get('from_value', ''),
                conflict.get('to_value', ''),
                conflict['app_user_creation_id'],
                conflict['app_user_update_id'],
                conflict.get('creation_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                conflict.get('update_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                conflict.get('status', 1)
            ))

        query = """
        INSERT INTO conflicto (
            Id, IdVersion, IdUsuario, IdSapPerfil, IdSapAutorizacion, IdSapRol,
            IdRiesgoActividadTransaccion, IdRiesgo, IdActividad, IdTransaccion,
            IdSapObjetoProceso, IdSapCampoProceso, Desde, Hasta,
            IdAppUserCreacion, IdAppUserActualizacion, FechaCreacion, FechaActualizacion, Estado
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """

        return self.execute_many(query, formatted_data, batch_size)
    
    def insert_conflict_results(self, job_id, id_version, total_time, conflict_count, user_id):
        return self.execute_procedure(
            'SP_INSERT_CONFLICT_RESULTS',
            params=(job_id, id_version, total_time, conflict_count, user_id)
        )