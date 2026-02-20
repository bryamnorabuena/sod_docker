from datetime import datetime
from typing import Optional

class Process:
    def __init__(
        self,
        process_id: int,
        rule_id: int,
        name: str,
        description: Optional[str],
        processed: bool,
        time: Optional[float],
        quantity: int,
        quantity_sa: int,
        app_user_creation_id: int,
        app_user_update_id: int,
        #creation_date: datetime,
        #update_date: datetime,
        #status: str
    ):
        self.process_id = process_id
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.processed = processed
        self.time = time
        self.quantity = quantity
        self.quantity_sa = quantity_sa
        self.app_user_creation_id = app_user_creation_id
        self.app_user_update_id = app_user_update_id
        #self.creation_date = creation_date
        #self.update_date = update_date
        #self.status = status

    @classmethod
    def from_dict(cls, data: dict):        
        return cls(
            process_id=data.get("PROCESS_ID"),
            rule_id=data.get("RULE_ID"),
            name=data.get("NAME"),
            description=data.get("DESCRIPTION"),
            processed=bool(data.get("PROCESSED", 0)),
            time=float(data["TIME"]) if data.get("TIME") is not None else None,
            quantity=int(data.get("QUANTITY", 0)),
            quantity_sa=int(data.get("QUANTITY_SA", 0)),
            app_user_creation_id=data.get("APP_USER_CREATION_ID"),
            app_user_update_id=data.get("APP_USER_UPDATE_ID"),
            #creation_date=cls._parse_datetime(data.get("CREATION_DATE")),
            #update_date=cls._parse_datetime(data.get("UPDATE_DATE")),
            #status=data.get("STATUS", "INACTIVE")
        )


