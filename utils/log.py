from utils.environment import get_environment
from datetime import datetime
from azure.data.tables import TableServiceClient
from flask import current_app

import uuid
import socket

def SaveStorage(session, ip, code, action, module, detail):
    tokendata = session
    serverConfig = get_environment('server')
    if get_environment('server')['envMode'] != "DEV":
        ym = datetime.now()
        my_entity = {
            'PartitionKey': serverConfig['appRoot'].replace("/", "").upper(),
            'RowKey': str(uuid.uuid4()),
            "user": tokendata['user'],
            "ip":   ip,
            "code": code,
            "action": action,
            "module": module,
            "detail": str(detail),
            "type": "BackEnd"
        }
        table_name = f"d{ym.strftime('%Y%m')}genyus{serverConfig['envMode'].split('-')[0]}appLog{tokendata['customer']}c{tokendata['contract']}"
        table_service_client = TableServiceClient.from_connection_string(conn_str=get_environment('connStrTable'))
        table_service_client.create_table_if_not_exists(table_name = table_name)
        table_client = table_service_client.get_table_client(table_name = table_name)
        table_client.create_entity(entity=my_entity)
    elif get_environment('server')['envMode'] == "DEV":
        logger = current_app.logger
        logger.info(f"action = {action} , module = {module} , code = {code} , detail = {detail} , ipaddress = {GetIpAddress()}")

def GetIpAddress():
  h_name = socket.gethostname()
  ip_address = socket.gethostbyname(h_name)
  return ip_address