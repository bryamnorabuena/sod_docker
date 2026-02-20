class Version:
    def __init__(self, id: int, process_id: int):
        self.id = id
        self.process_id = process_id

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get("VERSION_ID"),
            process_id=data.get("PROCESS_ID"),
        )