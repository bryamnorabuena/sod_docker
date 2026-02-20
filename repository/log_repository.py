from .base_repository import BaseRepository

class LogRepository(BaseRepository):
    def insert_log(self, message):
        response = self.execute_procedure(
            'SP_INSERT_LOG',
            params=(message,)
        )
        return response['data']