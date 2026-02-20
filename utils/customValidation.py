def white_space_rule(value):
  if isinstance(value, str):
    return len(value.strip()) > 0
  return False