from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.contrib.auth.models import User


class JWTCookieAuthentication(JWTAuthentication):
    #Custom authentication class that reads JWT from HTTP-only cookies
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                return self.get_validated_token(raw_token)
            
        access_token = request.COOKIES.get(settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'))

        if not access_token:
            return None
        
        try:
            validated_token = self.get_validated_token(access_token)
            return self.get_user(validated_token), validated_token
        except (InvalidToken, AuthenticationFailed):
            return None
        

def set_jwt_cookies(response, user):
    #Set JWT tokens as HTTP-only cookies in the response

    refresh = RefreshToken.for_user(user)

    response.set_cookie(
        key = settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'),
        value = str(refresh.access_token),
        httponly = settings.SIMPLE_JWT.get('AUTH_COOKIE_HTTP_ONLY', True),
        secure=settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', not settings.DEBUG),
        samesite = settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Strict'),
        max_age=settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME').total_seconds(),
        path=settings.SIMPLE_JWT.get('AUTH_COOKIE_PATH', '/'),
    )

    response.set_cookie(
        key=settings.SIMPLE_JWT.get('AUTH_COOKIE_REFRESH', 'refresh_token'),
        value=str(refresh),
        httponly=settings.SIMPLE_JWT.get('AUTH_COOKIE_HTTP_ONLY', True),
        secure=settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', not settings.DEBUG),
        samesite=settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Strict'),
        max_age=settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME').total_seconds(),
        path=settings.SIMPLE_JWT.get('AUTH_COOKIE_PATH', '/'),
    )

    return response


def delete_jwt_cookies(response):
    try:
        response.delete_cookie(settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'))
        response.delete_cookie(settings.SIMPLE_JWT.get('AUTH_COOKIE_REFRESH', 'refresh_token'))
        return response
    except Exception as e:
        print(f"JWT cookie error: {e}")
        return response