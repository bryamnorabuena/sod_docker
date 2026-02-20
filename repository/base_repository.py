# repositories/base_repository.py
import json

import pymysql
from utils.modExecuteDataQuerie import create_query_dict
from utils.environment import get_environment
from utils.log import SaveStorage, GetIpAddress
from flask import current_app, session

class BaseRepository:
    def __init__(self, db_alias='mysql'):
        self.db_alias = db_alias
        config = json.loads(get_environment('DB_CONNECTION', '{}'))
        self.db_settings = {'database': config}
    
    def execute_procedure(self, procedure_name, params=None, operation_type='sp'):
        result = None
        try:
            query = f"CALL {procedure_name}({','.join(['%s']*len(params)) if params else ''})"
            result = create_query_dict(
                self.db_settings['database'],
                operation_type,
                [[query]],
                params
            )            
            return {
                'success': True, 
                'data': result,
                'code': 200,
            }
        except Exception as e:
            return {
                'data': result,
                'success': False,
                'detail': f"Error: {procedure_name}"
            }
    
    def execute_many(self, query: str, params: list, batch_size: int = 1000):
        """
        Inserta/actualiza múltiples filas en lotes.
        - query: string SQL con placeholders (%s)
        - params: lista de tuplas con los valores
        - batch_size: cantidad de filas por lote
        """
        conn = pymysql.connect(**self.db_settings['database'])
        total_inserted = 0
        try:
            with conn.cursor() as cursor:
                for i in range(0, len(params), batch_size):
                    chunk = params[i:i + batch_size]
                    cursor.executemany(query, chunk)
                    total_inserted += len(chunk)
            conn.commit()
        finally:
            conn.close()
        
        return {"success": True, "inserted": total_inserted}
