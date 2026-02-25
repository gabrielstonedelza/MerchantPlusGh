from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from transactions.models import AgentRequest, ExpenseRequest
from transactions.serializers import AgentRequestSerializer
from customers.models import Customer
from accounts.models import Membership
from .models import SavedReport
from .serializers import SavedReportSerializer


# ---------------------------------------------------------------------------
# Dashboard Summary
# ---------------------------------------------------------------------------
@api_view(["GET"])
def dashboard(request):
    """Main dashboard endpoint for company owners/admins."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    company = membership.company
    today = timezone.now().date()

    today_reqs = AgentRequest.objects.filter(company=company, requested_at__date=today)

    total_requests_today = today_reqs.count()

    deposits_today = today_reqs.filter(
        transaction_type="deposit", status="approved"
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    withdrawals_today = today_reqs.filter(
        transaction_type="withdrawal", status="approved"
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    fees_today = today_reqs.filter(
        status="approved"
    ).aggregate(total=Sum("fee"))["total"] or Decimal("0")

    pending_approvals = AgentRequest.objects.filter(
        company=company, status="pending"
    ).count()

    total_customers = Customer.objects.filter(company=company, status="active").count()
    total_active_users = Membership.objects.filter(company=company, is_active=True).count()

    by_channel = {}
    for row in today_reqs.values("channel").annotate(count=Count("id")):
        by_channel[row["channel"]] = row["count"]

    by_status = {}
    for row in today_reqs.values("status").annotate(count=Count("id")):
        by_status[row["status"]] = row["count"]

    recent = AgentRequest.objects.filter(
        company=company
    ).select_related("approved_by", "customer").order_by("-requested_at")[:10]

    return Response({
        "total_requests_today": total_requests_today,
        "total_deposits_today": str(deposits_today),
        "total_withdrawals_today": str(withdrawals_today),
        "total_fees_today": str(fees_today),
        "pending_approvals": pending_approvals,
        "total_customers": total_customers,
        "total_active_users": total_active_users,
        "requests_by_channel": by_channel,
        "requests_by_status": by_status,
        "recent_requests": AgentRequestSerializer(recent, many=True).data,
    })


# ---------------------------------------------------------------------------
# Transaction Summary Report
# ---------------------------------------------------------------------------
@api_view(["GET"])
def transaction_summary(request):
    """Aggregated request report with filters."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    company = membership.company
    qs = AgentRequest.objects.filter(company=company, status="approved")

    date_from = request.query_params.get("date_from", str(date.today() - timedelta(days=30)))
    date_to = request.query_params.get("date_to", str(date.today()))
    qs = qs.filter(requested_at__date__gte=date_from, requested_at__date__lte=date_to)

    channel = request.query_params.get("channel")
    if channel:
        qs = qs.filter(channel=channel)

    tx_type = request.query_params.get("type")
    if tx_type:
        qs = qs.filter(transaction_type=tx_type)

    totals = qs.aggregate(
        total_count=Count("id"),
        total_amount=Sum("amount"),
        total_fees=Sum("fee"),
    )

    by_type = list(qs.values("transaction_type").annotate(
        count=Count("id"), total=Sum("amount"), fees=Sum("fee"),
    ))

    by_channel = list(qs.values("channel").annotate(
        count=Count("id"), total=Sum("amount"),
    ))

    daily = list(
        qs.values("requested_at__date")
        .annotate(count=Count("id"), total=Sum("amount"))
        .order_by("requested_at__date")
    )
    daily_trend = [
        {"date": str(row["requested_at__date"]), "count": row["count"], "total": str(row["total"] or 0)}
        for row in daily
    ]

    return Response({
        "period": {"from": date_from, "to": date_to},
        "totals": {
            "count": totals["total_count"],
            "amount": str(totals["total_amount"] or 0),
            "fees": str(totals["total_fees"] or 0),
        },
        "by_type": by_type,
        "by_channel": by_channel,
        "daily_trend": daily_trend,
    })


# ---------------------------------------------------------------------------
# Request Volume Report (replaces agent_performance — no initiated_by field)
# ---------------------------------------------------------------------------
@api_view(["GET"])
def agent_performance(request):
    """Request volume breakdown by type and channel."""
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
    )

    by_type = list(qs.values("transaction_type").annotate(
        count=Count("id"),
        total_amount=Sum("amount"),
        total_fees=Sum("fee"),
        approved=Count("id", filter=Q(status="approved")),
        pending=Count("id", filter=Q(status="pending")),
        rejected=Count("id", filter=Q(status="rejected")),
    ))

    by_channel = list(qs.values("channel").annotate(
        count=Count("id"),
        total_amount=Sum("amount"),
    ))

    return Response({
        "period": {"from": date_from, "to": date_to},
        "by_type": by_type,
        "by_channel": by_channel,
    })


# ---------------------------------------------------------------------------
# Revenue Report
# ---------------------------------------------------------------------------
@api_view(["GET"])
def revenue_report(request):
    """Revenue from fees."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    company = membership.company
    date_from = request.query_params.get("date_from", str(date.today() - timedelta(days=30)))
    date_to = request.query_params.get("date_to", str(date.today()))

    qs = AgentRequest.objects.filter(
        company=company, status="approved",
        requested_at__date__gte=date_from, requested_at__date__lte=date_to,
    )

    total_fees = qs.aggregate(total=Sum("fee"))["total"] or Decimal("0")
    fees_by_channel = list(qs.values("channel").annotate(fees=Sum("fee")).order_by("-fees"))
    fees_by_type = list(qs.values("transaction_type").annotate(fees=Sum("fee")).order_by("-fees"))

    daily = list(
        qs.values("requested_at__date").annotate(fees=Sum("fee")).order_by("requested_at__date")
    )
    daily_trend = [
        {"date": str(row["requested_at__date"]), "fees": str(row["fees"] or 0)}
        for row in daily
    ]

    expenses = ExpenseRequest.objects.filter(
        company=company, status__in=["approved", "paid"],
        created_at__date__gte=date_from, created_at__date__lte=date_to,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    return Response({
        "period": {"from": date_from, "to": date_to},
        "total_fees": str(total_fees),
        "total_expenses": str(expenses),
        "net_revenue": str(total_fees - expenses),
        "fees_by_channel": fees_by_channel,
        "fees_by_type": fees_by_type,
        "daily_trend": daily_trend,
    })


# ---------------------------------------------------------------------------
# Saved Reports
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
def saved_reports(request):
    """List or create saved report configurations."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        qs = SavedReport.objects.filter(company=membership.company)
        return Response(SavedReportSerializer(qs, many=True).data)

    serializer = SavedReportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(company=membership.company, created_by=request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
def delete_saved_report(request, report_id):
    """Delete a saved report."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        report = SavedReport.objects.get(id=report_id, company=membership.company)
    except SavedReport.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if report.created_by != request.user and membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    report.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
