from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import SecurityRule
from dotenv import load_dotenv
from utils.environment import get_environment
import os
import logging
import requests

def update_nsg_if_needed():
    try:
        # subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        # resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        # nsg_name = "vm-seg-funciones-nsg"

        # rule_name = os.getenv("AZURE_RULE_NAME")
        # rule_priority = os.getenv("AZURE_PRIORITY")
        # destination_port = os.getenv("AZURE_DESTINATION_PORT")

        environment = get_environment('FLASK_ENV')

        subscription_id = get_environment("AZURE_SUBSCRIPTION_ID")
        resource_group = get_environment("AZURE_RESOURCE_GROUP")
        nsg_name = "vm-seg-funciones-nsg"

        rule_name = get_environment("AZURE_RULE_NAME")
        rule_priority = get_environment("AZURE_PRIORITY")
        destination_port = get_environment("AZURE_DESTINATION_PORT")

        logging.info(f"subscription_id: {subscription_id}")
        logging.info(f"resource_group: {resource_group}")
        logging.info(f"nsg_name: {nsg_name}")

        return True

        if environment == 'local':
            print("Entorno local detectado, no se actualizará la regla de seguridad.")
            return True

        source_ip  = requests.get("https://ipinfo.io/json", verify=False).json()["ip"]
        print(f"IP pública detectada: {source_ip}")

        credential = DefaultAzureCredential()

        network_client = NetworkManagementClient(credential, subscription_id)

        security_rule = SecurityRule(
            name=rule_name,
            protocol="Tcp",
            direction="Inbound",
            access="Allow",
            priority=rule_priority,
            source_address_prefix=source_ip,
            source_port_range="*",
            destination_address_prefix="*",
            destination_port_range=destination_port,
        )
        logging.info(f"Regla de seguridad: {security_rule}")

        async_nsg_update = network_client.security_rules.begin_create_or_update(
            resource_group_name=resource_group,
            network_security_group_name=nsg_name,
            security_rule_name=rule_name,
            security_rule_parameters=security_rule,
        )

        async_nsg_update.result()
        return True      

    except Exception as e:
        print(f"Error al actualizar la regla: {str(e)}")
        logging.error(f"Error al actualizar la regla: {str(e)}")
        return str(e)









