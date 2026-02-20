from repository.app_user_repository import AppUserRepository
from flask import current_app

from repository.mapping.app_user import AppUser

class AppUserService:
    def __init__(self):
        self.repository = AppUserRepository()

    def find_user_app(self, id_version):
        try:
            repository_response = self.repository.find_user_app(id_version)            
            return AppUser.from_dict(repository_response[0])
        
        except Exception as e:
            raise Exception(f"Error al buscar el usuario: {str(e)}")
    
    def find_all_users(self):
        try:
            users_list = self.repository.find_all_clients()
            return [AppUser.from_dict(user) for user in users_list if user]
            
        except Exception as e:
            raise Exception(f"Error al buscar los usuarios: {str(e)}")