import base64
import re

def is_base64(value):
    # Verifica si el string tiene caracteres válidos para Base64
    if not re.fullmatch(r'^[A-Za-z0-9+/]*={0,2}$', value):
        return False
    
    try:
        # Intenta decodificar
        base64.b64decode(value, validate=True)
        return True
    except (base64.binascii.Error, ValueError):
        return False