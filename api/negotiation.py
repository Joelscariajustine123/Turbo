from rest_framework.exceptions import NotAcceptable
from rest_framework.negotiation import DefaultContentNegotiation


class JSONFallbackNegotiation(DefaultContentNegotiation):
    """Answer with JSON instead of a 406 error when the client asks for something else.

    In production only the JSON renderer is enabled, so a browser opening an API
    URL (Accept: text/html) still gets readable JSON.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        try:
            return super().select_renderer(request, renderers, format_suffix)
        except NotAcceptable:
            return renderers[0], renderers[0].media_type
