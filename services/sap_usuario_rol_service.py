from repository.sap_user_rol_repository import SapUsuarioRolRepository
from repository.mapping.sap_usuario_rol import SapUsuarioRol

class SapUsuarioRolService:
    def __init__(self):
        self.repository = SapUsuarioRolRepository()

    def get_active_group_user_profile_by_process_user(self, usuario_rol_id):
        try:
            repository_response = self.repository.get_user_profile_by_process_user(usuario_rol_id)           
            return [SapUsuarioRol.from_dict(repository_response) for user in repository_response if user]
        except Exception as e:
            raise Exception(f"Error al buscar el perfil de usuario: {str(e)}")