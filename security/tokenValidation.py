from utils.environment import get_environment
from utils.log import SaveStorage, GetIpAddress
from mockups.token import mockup_data

import http.client
import json

class TokenAuthenticationError(SystemError):
  '''raise this when there's a authentication error'''

def token_valid(app, session, abort, token, without_refresh = False):
  try:
    logger = app.logger
    logger.info("Authenticating...")
    server_configuration = json.loads(get_environment('server'))

    if server_configuration['envMode'] == "DEV":
      data = mockup_data['009']
    else:
      data = auth_session(token, without_refresh)

    if data["status"] == "Success":
      session['token'] = token
      session['tokenData'] = data
      SaveStorage(session['tokenData'], GetIpAddress(), 200, "token_valid", "tokenvalidation", "Authenticated")
    else:
      raise TokenAuthenticationError("Authentication Required")
  except TokenAuthenticationError as e:
    logger.info(f"Invalid token: {e}")
    abort(401)
  except Exception as e:
    logger.info(f"Validating token: {e}")
    abort(503)

def auth_session(token, without_refresh = False):
    import ssl

    ssl._create_default_https_context = ssl._create_unverified_context
    connection = http.client.HTTPSConnection(get_environment('restServerSec'))
    header = {
      'token': token
    }
    path = "getSessionInformationV2" if not without_refresh else "valid_session_information"
    connection.request("POST", "/appSecServ/" + path, headers=header)
    response = connection.getresponse()
    data = response.read().decode("UTF-8")
    connection.close()
    return json.loads(data)