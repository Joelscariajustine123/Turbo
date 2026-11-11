from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def _first_message(data):
    if isinstance(data, str):
        return data
    if isinstance(data, list) and data:
        return _first_message(data[0])
    if isinstance(data, dict) and data:
        if 'detail' in data:
            return _first_message(data['detail'])
        key, value = next(iter(data.items()))
        msg = _first_message(value)
        return msg if key == 'non_field_errors' else f"{key.replace('_', ' ').capitalize()}: {msg}"
    return "Something went wrong."


def exception_handler(exc, context):
    """Every error response has a human-readable `detail` string clients can show as-is.

    Service functions raise Django's ValidationError; those become HTTP 400 with
    `detail` (first message) and `errors` (all messages).
    """
    if isinstance(exc, DjangoValidationError):
        return Response({'detail': exc.messages[0], 'errors': exc.messages}, status=400)

    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(response.data, (dict, list)):
        data = response.data
        if not (isinstance(data, dict) and isinstance(data.get('detail'), str)):
            response.data = {'detail': _first_message(data), 'errors': data}
    return response
