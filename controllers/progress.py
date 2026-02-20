from flask import Blueprint, request, jsonify
from utils import storage

progress = Blueprint('progress', __name__)

@progress.route('/getStatus', methods = ['GET'], )
def process_form():
    try:
        body = request.args
        job_id = body['id']

        if job_id is None:
            return jsonify({'error': 'Falta Job Id'}), 400
        
        status = storage.get_status(job_id)
        
        return jsonify(status), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500