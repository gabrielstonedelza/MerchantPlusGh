from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed


class CookieTokenAuthentication(TokenAuthentication):
    """
    DRF authentication class that reads the auth token from the
    httpOnly 'auth_token' cookie first, then falls back to the
    standard Authorization header.
    """

    def authenticate(self, request):
        token_key = request.COOKIES.get('auth_token')
        if not token_key:
            return super().authenticate(request)
        try:
            token = Token.objects.select_related('user').get(key=token_key)
        except Token.DoesNotExist:
            raise AuthenticationFailed('Invalid token.')
        if not token.user.is_active:
            raise AuthenticationFailed('User inactive.')
        return (token.user, token)
