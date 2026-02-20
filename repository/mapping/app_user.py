class AppUser:
    def __init__(
        self,
        app_user_id: int,
        first_name: str,
        last_name: str,
        username: str,
        email: str,
    ):
        self.app_user_id = app_user_id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.email = email

    @classmethod
    def from_dict(cls, data: dict):
        return cls (
            app_user_id = data.get("APP_USER_ID"),
            first_name=data.get("FIRST_NAME"),
            last_name=data.get("LAST_NAME"),
            username=data.get("USERNAME"),
            email=data.get("EMAIL"),
        )