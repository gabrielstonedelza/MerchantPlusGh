"""
Webhook management API views.
"""

import secrets
from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .webhooks import WebhookEndpoint, WebhookDelivery, dispatch_webhook


@api_view(["GET", "POST"])
def webhook_endpoints(request):
    """List or create webhook endpoints. Admin+ only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    if not membership.company.subscription_plan.has_api_access:
        return Response(
            {"error": "Webhooks require API access. Upgrade your plan."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        qs = WebhookEndpoint.objects.filter(company=membership.company)
        data = [
            {
                "id": str(e.id),
                "url": e.url,
                "events": e.events,
                "is_active": e.is_active,
                "failure_count": e.failure_count,
                "last_triggered_at": e.last_triggered_at,
                "created_at": e.created_at,
            }
            for e in qs
        ]
        return Response(data)

    # POST — create new endpoint
    url = request.data.get("url")
    events = request.data.get("events", [])

    if not url:
        return Response(
            {"error": "URL is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    secret = WebhookEndpoint.generate_secret()
    endpoint = WebhookEndpoint.objects.create(
        company=membership.company,
        url=url,
        secret=secret,
        events=events,
    )

    return Response(
        {
            "id": str(endpoint.id),
            "url": endpoint.url,
            "secret": secret,  # Only shown once on creation
            "events": endpoint.events,
            "message": "Save the secret — it won't be shown again.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["DELETE"])
def delete_webhook_endpoint(request, endpoint_id):
    """Delete a webhook endpoint. Admin+ only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id, company=membership.company)
    except WebhookEndpoint.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    endpoint.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def webhook_deliveries(request, endpoint_id):
    """List recent deliveries for a webhook endpoint. Admin+ only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id, company=membership.company)
    except WebhookEndpoint.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    deliveries = WebhookDelivery.objects.filter(endpoint=endpoint)[:50]
    data = [
        {
            "id": str(d.id),
            "event_type": d.event_type,
            "status": d.status,
            "response_status_code": d.response_status_code,
            "attempts": d.attempts,
            "created_at": d.created_at,
        }
        for d in deliveries
    ]

    return Response(data)


@api_view(["GET"])
def webhook_stats(request):
    """Webhook delivery statistics. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    company_endpoints = WebhookEndpoint.objects.filter(company=membership.company)
    company_deliveries = WebhookDelivery.objects.filter(
        endpoint__company=membership.company
    )

    total = company_deliveries.count()
    by_status = dict(
        company_deliveries.values("status")
        .annotate(count=Count("id"))
        .values_list("status", "count")
    )
    top_events = list(
        company_deliveries.values("event_type")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    return Response({
        "total_deliveries": total,
        "by_status": by_status,
        "top_event_types": top_events,
        "registered_endpoints": company_endpoints.filter(is_active=True).count(),
    })


@api_view(["POST"])
def webhook_test_ping(request, endpoint_id):
    """Send a test ping event to a webhook endpoint. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        endpoint = WebhookEndpoint.objects.get(
            id=endpoint_id, company=membership.company
        )
    except WebhookEndpoint.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    dispatch_webhook(
        company_id=str(membership.company.id),
        event_type="ping",
        data={"message": "MerchantPlus webhook test ping"},
    )
    return Response({"detail": "Test ping dispatched."})
