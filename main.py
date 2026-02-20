import json
import os
import ssl
from logging.config import dictConfig
from flask import Flask, jsonify, request, abort
from base64 import b64decode
from werkzeug.exceptions import BadRequest, Unauthorized, Conflict, ServiceUnavailable
from json import dumps
from utils.environment import load_environment, get_environment

env_mode = os.getenv("APP_ENV", "local")
load_environment(env_mode)

from controllers.conflict import conflict
from controllers.conflict2 import conflict2
from controllers.progress import progress
from controllers.rule import rule
from controllers.matrixsap import matrixsap
from controllers.process import process
from controllers.test import test
from jobs.conflict import job_analize_conflicts
from utils.validation import validate_input
from utils.environment import load_environment, get_environment


server_environment = json.loads(get_environment('SERVER'))

dictConfig({
  'version': 1,
  'formatters': {
    'default': {
      'format': '[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s'
    }
  },
  'handlers': {
    'wsgi': {
      'class': 'logging.StreamHandler',
      'stream': 'ext://flask.logging.wsgi_errors_stream',
      'formatter': 'default'
    }
  },
  'root': {
    'level': 'INFO',
    'handlers': ['wsgi']
  }
})

app = Flask(__name__)
app.config['SESSION_COOKIE_NAME'] = server_environment['sessionName']
app.config['SESSION_COOKIE_SECURE'] = True
app.secret_key = b64decode(server_environment['secret'])

app.register_blueprint(progress, url_prefix = server_environment['appRoot']+ '/progress')
app.register_blueprint(conflict, url_prefix = server_environment['appRoot'] + '/conflict')
app.register_blueprint(rule, url_prefix = server_environment['appRoot'] + '/rule')
app.register_blueprint(matrixsap, url_prefix = server_environment['appRoot'] + '/matrixsap')
app.register_blueprint(process, url_prefix = server_environment['appRoot'] + '/process')
app.register_blueprint(test, url_prefix = server_environment['appRoot'] + '/test')

app.register_blueprint(conflict2, url_prefix = server_environment['appRoot'] + '/conflict2')

CONTENT_TYPE = "application/json"

@app.get("/health")
def health():
    # Opcional: agrega chequeos a BBDD, caches, etc.
    return jsonify(status="ok"), 200

@app.errorhandler(BadRequest)
def handle_bad_request(e):
  """Return JSON instead of HTML for HTTP errors."""
  response = e.get_response()
  response.data = dumps({
    "status": "Error",
    "detail": e.name,
    "data": {},
  })
  response.content_type = CONTENT_TYPE
  return response

@app.errorhandler(Unauthorized)
def handle_unauthorized(e):
  """Return JSON instead of HTML for HTTP errors."""
  response = e.get_response()
  response.data = dumps({
    "status": "Error",
    "detail": e.name,
    "data": {},
  })
  response.content_type = CONTENT_TYPE
  return response


@app.errorhandler(Conflict)
def handle_conflict(e):
  """Return JSON instead of HTML for HTTP errors."""
  # start with the correct headers and status code from the error
  response = e.get_response()
  # replace the body with JSON
  response.data = dumps({
    "status": "Error",
    "detail": e.name,
    "data": {},
  })
  response.content_type = CONTENT_TYPE
  return response

@app.errorhandler(ServiceUnavailable)
def handle_service_unavailable(e):
  """Return JSON instead of HTML for HTTP errors."""
  # start with the correct headers and status code from the error
  response = e.get_response()
  # replace the body with JSON
  response.data = dumps({
    "status": "Error",
    "detail": e.name,
    "data": {},
  })
  response.content_type = CONTENT_TYPE
  return response

@app.before_request
def sanitize_body():
  ignored_fields = ['token']
  exclude_paths = ['appSecServ', 'uploadFile', 'editFile','downloadProject', 'downloadFile', 'downloadFolder', 'downloadActivity', 'downloadStage']
  if any(path in request.path for path in exclude_paths) or request.method == 'GET':
      return
  data = request.json
  for key, value in data.items():
      if key not in ignored_fields:
          if not validate_input(str(value)):
              print('request invalido')
              abort(400)

if __name__ == '__main__':
  port = int(os.environ.get("PORT", 8000))
  app.run(host="0.0.0.0", port=port)