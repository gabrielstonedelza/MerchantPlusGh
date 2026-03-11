from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import FraudRule, FraudSignal, FraudAuditLog
from .serializers import (
    FraudRuleSerializer, FraudSignalSerializer,
    FraudSignalResolveSerializer, FraudRiskSummarySerializer,
)
from .engine import FraudEngine


# ── Rules ──────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
def fraud_rules(request):
    """List or create fraud rules. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        rules = FraudRule.objects.filter(
            company=membership.company
        ).order_by("-created_at")
        return Response(FraudRuleSerializer(rules, many=True).data)

    serializer = FraudRuleSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(company=membership.company)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "DELETE"])
def fraud_rule_detail(request, rule_id):
    """Get, update, or delete a fraud rule. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    rule = get_object_or_404(FraudRule, pk=rule_id, company=membership.company)

    if request.method == "GET":
        return Response(FraudRuleSerializer(rule).data)

    if request.method == "PUT":
        serializer = FraudRuleSerializer(rule, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    rule.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── Signals ────────────────────────────────────────────────────────────

@api_view(["GET"])
def fraud_signals(request):
    """List fraud signals with optional filters. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    qs = FraudSignal.objects.filter(
        company=membership.company
    ).select_related("rule").order_by("-triggered_at")

    # Optional filters
    bank = request.query_params.get("bank")
    severity = request.query_params.get("severity")
    signal_status = request.query_params.get("status")
    customer = request.query_params.get("customer")

    if bank:
        qs = qs.filter(bank=bank)
    if severity:
        qs = qs.filter(severity=severity)
    if signal_status:
        qs = qs.filter(status=signal_status)
    if customer:
        qs = qs.filter(customer__icontains=customer)

    return Response(FraudSignalSerializer(qs[:200], many=True).data)


@api_view(["GET"])
def fraud_signal_detail(request, signal_id):
    """Get a single fraud signal with audit logs. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    signal = get_object_or_404(
        FraudSignal, pk=signal_id, company=membership.company,
    )
    return Response(FraudSignalSerializer(signal).data)


@api_view(["POST"])
def fraud_signal_resolve(request, signal_id):
    """Resolve a fraud signal (review, confirm, dismiss). Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    signal = get_object_or_404(
        FraudSignal, pk=signal_id, company=membership.company,
    )
    serializer = FraudSignalResolveSerializer(data=request.data)

    if serializer.is_valid():
        data = serializer.validated_data
        reviewer = request.user.full_name if request.user else "admin"
        signal.resolve(
            status=data["status"],
            reviewer=reviewer,
            notes=data.get("review_notes", ""),
        )
        FraudAuditLog.objects.create(
            signal=signal,
            action=data["status"],
            performed_by=reviewer,
            notes=data.get("review_notes", ""),
        )
        return Response(FraudSignalSerializer(signal).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Risk Summary Dashboard ─────────────────────────────────────────────

@api_view(["GET"])
def fraud_risk_summary(request):
    """Get risk summary stats for the dashboard. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    bank = request.query_params.get("bank")
    summary = FraudEngine.get_risk_summary(
        company=membership.company, bank=bank,
    )
    return Response(FraudRiskSummarySerializer(summary).data)


# ── Manual scan trigger ────────────────────────────────────────────────

@api_view(["POST"])
def fraud_manual_scan(request):
    """
    Trigger fraud engine manually against an AgentRequest.
    Body: { "transaction_id": "<uuid>" }
    """
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    tx_id = request.data.get("transaction_id")
    if not tx_id:
        return Response(
            {"error": "transaction_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from transactions.models import AgentRequest
        req = AgentRequest.objects.get(pk=tx_id, company=membership.company)
        signals = FraudEngine.analyse_transaction(req)
    except AgentRequest.DoesNotExist:
        return Response(
            {"error": "Transaction not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        "signals_triggered": len(signals),
        "signals": FraudSignalSerializer(signals, many=True).data,
    })
