"""
CSV export for Merchant+ reports.

Endpoints:
  GET /api/v1/reports/export/transactions/  → CSV download
  GET /api/v1/reports/export/summary/       → CSV download (by type/channel)
"""

import csv
from datetime import date, timedelta
from django.db.models import Sum, Count

from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from transactions.models import AgentRequest


@api_view(["GET"])
def export_transactions_csv(request):
    """Export agent requests as CSV. Manager+ only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    company = membership.company
    date_from = request.query_params.get("date_from", str(date.today() - timedelta(days=30)))
    date_to = request.query_params.get("date_to", str(date.today()))

    qs = AgentRequest.objects.filter(
        company=company,
        requested_at__date__gte=date_from,
        requested_at__date__lte=date_to,
    ).select_related(
        "approved_by", "customer",
        "bank_deposit_detail", "momo_detail",
    ).order_by("-requested_at")

    tx_status = request.query_params.get("status")
    if tx_status:
        qs = qs.filter(status=tx_status)

    tx_type = request.query_params.get("type")
    if tx_type:
        qs = qs.filter(transaction_type=tx_type)

    channel = request.query_params.get("channel")
    if channel:
        qs = qs.filter(channel=channel)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="agent_requests_{date_from}_to_{date_to}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        "Reference", "Requested At", "Type", "Channel", "Status",
        "Amount (GHS)", "Fee (GHS)", "Customer", "Approved By",
    ])

    for req in qs[:5000]:
        writer.writerow([
            req.reference,
            req.requested_at.strftime("%Y-%m-%d %H:%M:%S"),
            req.transaction_type,
            req.channel,
            req.status,
            str(req.amount),
            str(req.fee),
            req.customer.full_name if req.customer else "Walk-in",
            req.approved_by.full_name if req.approved_by else "-",
        ])

    return response


@api_view(["GET"])
def export_agents_csv(request):
    """Export request volume summary by type and channel as CSV. Manager+ only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    company = membership.company
    date_from = request.query_params.get("date_from", str(date.today() - timedelta(days=30)))
    date_to = request.query_params.get("date_to", str(date.today()))

    by_type = (
        AgentRequest.objects.filter(
            company=company,
            requested_at__date__gte=date_from,
            requested_at__date__lte=date_to,
        )
        .values("transaction_type", "channel", "status")
        .annotate(count=Count("id"), total_amount=Sum("amount"), total_fees=Sum("fee"))
        .order_by("transaction_type", "channel", "status")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="request_summary_{date_from}_to_{date_to}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        "Type", "Channel", "Status", "Count",
        "Total Amount (GHS)", "Total Fees (GHS)",
    ])

    for row in by_type:
        writer.writerow([
            row["transaction_type"],
            row["channel"],
            row["status"],
            row["count"],
            str(row["total_amount"] or 0),
            str(row["total_fees"] or 0),
        ])

    return response
