import re
from utils import base64

NORMAL_TEXT_REGEX = r"^[\w \-\(\)áéíóúñÁÉÍÓÚÑ'#.,&@$¿+%=?;:{}\[\]\"/=]*$"
# Si quieres tabs/newlines, usa la versión con \s

regex = re.compile(NORMAL_TEXT_REGEX)

def validate_input(data):
  if data is None or data == "":
    return False
  # elif len(data) > 255:
  #   return False
  else:
    if base64.is_base64(data) == False:
      regex = re.compile(NORMAL_TEXT_REGEX)
      if re.fullmatch(regex, data) is None:
        print("regex")
        return False
      else:
        return True
    else:
      return True