from utils.log import SaveStorage, GetIpAddress
from flask import session

class RoleNotAuthorizedError(SystemError):
  '''raise this when there's a role error'''

def role_valid(app, abort, user_roles, allowed_roles):
  try:
    SaveStorage(session['tokenData'], GetIpAddress(), 200, "role_valid", "rolevalidation", "Cheking Role...")
    found_roles = list(set(user_roles) & set(allowed_roles))

    if len(found_roles) > 0:
      SaveStorage(session['tokenData'], GetIpAddress(), 200, "role_valid", "rolevalidation", "Role authorized")
      return
    else:
      raise RoleNotAuthorizedError("Role not authorized")
  except Exception as e:
    SaveStorage(session['tokenData'], GetIpAddress(), 401, "role_valid", "rolevalidation", f"User doesn't have the appropriate role: {e}")
    abort(401)