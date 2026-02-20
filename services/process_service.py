from repository.process_repository import ProcessRepository
from repository.mapping.process import Process
class ProcessService:
    def __init__(self):
        self.repository = ProcessRepository()

    def find_process_by_id(self, process_id):
        try:
            repository_response = self.repository.find_process_by_id(process_id)
            ##print(f"repository_response: {repository_response}")
            return Process.from_dict(repository_response[0])

        except Exception as e:
            raise Exception(f"Error al buscar el proceso: {str(e)}")