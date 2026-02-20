from .base_repository import BaseRepository

class AppUserRepository(BaseRepository):
    def find_user_app(self, id_version):
        response = self.execute_procedure(
            'SP_FIND_APP_USER_BY_ID',
            params=(id_version,)
            )        
        return response['data']
    
    def find_all_clients(self):
        response = self.execute_procedure(
            'SP_GET_ALL_USERS'
            )       
        return response['data']