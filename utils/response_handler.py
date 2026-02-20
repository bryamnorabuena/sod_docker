from flask import jsonify

class BaseResponse:
    @staticmethod
    def success(data=None, http_code=200):
        return jsonify({
            'status': 'success',
            'code': http_code,
            'data': data
        }), http_code

    @staticmethod
    def error(message="Error", http_code=400, details=None):
        response = {
            'status': 'error',
            'code': http_code,
            'message': message
        }
        if details:
            response['details'] = details
        return jsonify(response), http_code

    @staticmethod
    def from_service(service_result):
        if service_result['success']:
            return BaseResponse.success(
                data=service_result.get('data'),
                http_code=service_result.get('code', 200)
            )
        return BaseResponse.error(
            message=service_result.get('error'),
            http_code=service_result.get('code', 500),
            detail=service_result.get('detail')
        )