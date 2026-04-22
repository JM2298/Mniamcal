from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    error_code = 'ERROR'
    if hasattr(exc, 'get_codes'):
        codes = exc.get_codes()
        if isinstance(codes, dict) or isinstance(codes, list):
            error_code = 'VALIDATION_ERROR'
        elif isinstance(codes, str):
            error_code = codes.upper()
    elif hasattr(exc, 'default_code') and isinstance(exc.default_code, str):
        error_code = exc.default_code.upper()

    detail = ''
    errors = None
    if isinstance(response.data, dict):
        detail = str(response.data.get('detail', ''))
        if 'detail' not in response.data:
            errors = response.data
    else:
        detail = str(response.data)

    payload = {'CODE': error_code}
    if detail:
        payload['detail'] = detail
    if errors is not None:
        payload['errors'] = errors

    response.data = payload
    return response
