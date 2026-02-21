"""
Tenant Context Middleware.

Attaches the user's active membership (and thus company) to every request.
All views can then access request.membership to scope queries.

The company is resolved from the X-Company-ID header or falls back to the
user's only active membership.

Note: DRF's TokenAuthentication runs at the view level, not in middleware.
This middleware resolves the token manually so that request.membership is
available before the view runs.
"""


def _resolve_user(request):
    """
    Return the authenticated user from either:
    - Django session (already set by AuthenticationMiddleware), or
    - DRF Authorization: Token <key> header.
    """
    if request.user and request.user.is_authenticated:
        return request.user

    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Token "):
        key = auth_header[6:].strip()
        try:
            from rest_framework.authtoken.models import Token
            token_obj = Token.objects.select_related("user").get(key=key)
            if token_obj.user.is_active:
                return token_obj.user
        except Exception:
            pass

    return None


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = None
        request.company = None

        user = _resolve_user(request)
        if user:
            from accounts.models import Membership

            company_id = request.META.get("HTTP_X_COMPANY_ID")

            if company_id:
                try:
                    membership = Membership.objects.select_related(
                        "company", "company__subscription_plan", "branch"
                    ).get(
                        user=user, company_id=company_id, is_active=True,
                    )
                    request.membership = membership
                    request.company = membership.company
                except Membership.DoesNotExist:
                    pass
            else:
                memberships = Membership.objects.select_related(
                    "company", "company__subscription_plan", "branch"
                ).filter(user=user, is_active=True)

                if memberships.count() == 1:
                    request.membership = memberships.first()
                    request.company = request.membership.company

        response = self.get_response(request)
        return response
