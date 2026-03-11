"""
MerchantPlus Fraud Signal Engine
Analyses AgentRequest transactions against active FraudRules.
Call FraudEngine.analyse_transaction() after every create/approve action.
"""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count

from .models import FraudRule, FraudSignal, FraudAuditLog


def _get_agent_request_model():
    from django.apps import apps
    return apps.get_model("transactions", "AgentRequest")


class FraudEngine:

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    @classmethod
    def analyse_transaction(cls, agent_request) -> list[FraudSignal]:
        """Run all active rules against an AgentRequest instance."""
        company = agent_request.company
        rules = FraudRule.objects.filter(company=company, is_active=True)

        # Scope rules by bank: global rules (bank="") OR matching bank
        if agent_request.bank:
            from django.db.models import Q
            rules = rules.filter(Q(bank="") | Q(bank=agent_request.bank))

        signals = []
        for rule in rules:
            signal = cls._run_rule(rule, agent_request)
            if signal:
                signals.append(signal)
                cls._log_audit(signal, "auto_detected", "system")

        return signals

    # ------------------------------------------------------------------
    # Rule runner
    # ------------------------------------------------------------------

    @classmethod
    def _run_rule(cls, rule: FraudRule, req) -> FraudSignal | None:
        handler = {
            "velocity": cls._check_velocity,
            "amount_spike": cls._check_amount_spike,
            "odd_hours": cls._check_odd_hours,
            "dormant_account": cls._check_dormant_account,
            "cross_bank": cls._check_cross_bank,
        }.get(rule.rule_type)

        if not handler:
            return None
        return handler(rule, req)

    # ------------------------------------------------------------------
    # Individual detectors
    # ------------------------------------------------------------------

    @classmethod
    def _check_velocity(cls, rule: FraudRule, req) -> FraudSignal | None:
        """Flag if customer submits too many requests within the time window."""
        AgentRequest = _get_agent_request_model()
        window_start = timezone.now() - timedelta(minutes=rule.threshold_window_minutes)

        qs = AgentRequest.objects.filter(
            company=req.company,
            requested_at__gte=window_start,
        )
        if req.customer_id:
            qs = qs.filter(customer=req.customer)
        else:
            qs = qs.filter(requested_by=req.requested_by)

        count = qs.count()
        threshold = rule.threshold_count or 5

        if count >= threshold:
            customer_name = req.customer.full_name if req.customer else str(req.requested_by)
            return cls._create_signal(
                rule=rule,
                company=req.company,
                customer=customer_name,
                bank=req.bank,
                description=(
                    f"Velocity breach: {count} requests in "
                    f"{rule.threshold_window_minutes} min (limit {threshold})"
                ),
                risk_score=min(0.95, 0.5 + (count - threshold) * 0.1),
                related_id=req.id,
                related_type=req.transaction_type,
                evidence={
                    "request_count": count,
                    "window_minutes": rule.threshold_window_minutes,
                    "reference": req.reference,
                },
            )
        return None

    @classmethod
    def _check_amount_spike(cls, rule: FraudRule, req) -> FraudSignal | None:
        """Flag if request amount is significantly above customer's average."""
        if not req.customer_id:
            return None

        AgentRequest = _get_agent_request_model()
        avg_data = AgentRequest.objects.filter(
            company=req.company,
            customer=req.customer,
            status__in=["approved", "completed"],
        ).aggregate(avg=Avg("amount"), count=Count("id"))

        avg = avg_data["avg"] or 0
        count = avg_data["count"] or 0
        if count < 3 or avg == 0:
            return None  # not enough history

        spike_multiplier = float(rule.threshold_amount or 3)
        req_amount = float(req.amount)

        if req_amount > float(avg) * spike_multiplier:
            return cls._create_signal(
                rule=rule,
                company=req.company,
                customer=req.customer.full_name,
                bank=req.bank,
                description=(
                    f"Amount spike: GH\u20b5{req_amount:,.2f} vs avg "
                    f"GH\u20b5{float(avg):,.2f} ({req_amount / float(avg):.1f}\u00d7)"
                ),
                risk_score=min(0.99, 0.4 + (req_amount / float(avg)) * 0.08),
                related_id=req.id,
                related_type=req.transaction_type,
                evidence={
                    "amount": req_amount,
                    "customer_avg": float(avg),
                    "multiplier": round(req_amount / float(avg), 2),
                    "reference": req.reference,
                },
            )
        return None

    @classmethod
    def _check_odd_hours(cls, rule: FraudRule, req) -> FraudSignal | None:
        """Flag transactions submitted during odd hours."""
        hour = timezone.now().hour
        start, end = rule.odd_hour_start, rule.odd_hour_end

        # Handle midnight wrap: e.g. 22-05 means 22,23,0,1,2,3,4,5
        if start > end:
            in_window = hour >= start or hour <= end
        else:
            in_window = start <= hour <= end

        if in_window:
            customer_name = req.customer.full_name if req.customer else str(req.requested_by)
            return cls._create_signal(
                rule=rule,
                company=req.company,
                customer=customer_name,
                bank=req.bank,
                description=(
                    f"Odd-hour transaction at {hour:02d}:00 "
                    f"(flagged window {start:02d}:00\u2013{end:02d}:00)"
                ),
                risk_score=0.45,
                related_id=req.id,
                related_type=req.transaction_type,
                evidence={
                    "hour": hour,
                    "flag_window": f"{start}-{end}",
                    "reference": req.reference,
                },
            )
        return None

    @classmethod
    def _check_dormant_account(cls, rule: FraudRule, req) -> FraudSignal | None:
        """Flag if a customer's account was dormant before this request."""
        if not req.customer_id:
            return None

        AgentRequest = _get_agent_request_model()
        dormant_minutes = rule.threshold_window_minutes or (90 * 24 * 60)
        cutoff = timezone.now() - timedelta(minutes=dormant_minutes)

        last = (
            AgentRequest.objects.filter(
                company=req.company,
                customer=req.customer,
                status__in=["approved", "completed"],
            )
            .exclude(id=req.id)
            .order_by("-requested_at")
            .first()
        )

        if last and last.requested_at < cutoff:
            gap_days = (timezone.now() - last.requested_at).days
            return cls._create_signal(
                rule=rule,
                company=req.company,
                customer=req.customer.full_name,
                bank=req.bank,
                description=f"Dormant account reactivated after {gap_days} days of inactivity",
                risk_score=0.60,
                related_id=req.id,
                related_type=req.transaction_type,
                evidence={
                    "last_transaction": str(last.requested_at),
                    "gap_days": gap_days,
                    "reference": req.reference,
                },
            )
        return None

    @classmethod
    def _check_cross_bank(cls, rule: FraudRule, req) -> FraudSignal | None:
        """Flag if customer used multiple different banks in a short window."""
        if not req.customer_id or not req.bank:
            return None

        AgentRequest = _get_agent_request_model()
        window_start = timezone.now() - timedelta(minutes=rule.threshold_window_minutes)

        banks_used = list(
            AgentRequest.objects.filter(
                company=req.company,
                customer=req.customer,
                channel="bank",
                requested_at__gte=window_start,
            )
            .exclude(bank="")
            .values_list("bank", flat=True)
            .distinct()
        )

        threshold = rule.threshold_count or 3
        if len(banks_used) >= threshold:
            return cls._create_signal(
                rule=rule,
                company=req.company,
                customer=req.customer.full_name,
                bank=req.bank,
                description=(
                    f"Customer used {len(banks_used)} different banks "
                    f"in {rule.threshold_window_minutes} min"
                ),
                risk_score=0.75,
                related_id=req.id,
                related_type=req.transaction_type,
                evidence={
                    "banks": banks_used,
                    "window_minutes": rule.threshold_window_minutes,
                    "reference": req.reference,
                },
            )
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def _create_signal(cls, rule, company, customer, description, risk_score,
                       related_id, related_type, evidence,
                       bank="", phone="") -> FraudSignal:
        return FraudSignal.objects.create(
            company=company,
            customer=customer,
            phone=phone,
            bank=bank,
            rule=rule,
            signal_type=rule.rule_type,
            severity=rule.severity,
            description=description,
            risk_score=round(risk_score, 4),
            related_transaction_id=related_id,
            related_transaction_type=related_type,
            evidence=evidence,
        )

    @classmethod
    def _log_audit(cls, signal: FraudSignal, action: str, performer: str):
        FraudAuditLog.objects.create(
            signal=signal,
            action=action,
            performed_by=performer,
        )

    # ------------------------------------------------------------------
    # Risk summary helper for dashboard
    # ------------------------------------------------------------------

    @classmethod
    def get_risk_summary(cls, company, bank=None) -> dict:
        qs = FraudSignal.objects.filter(company=company, status="open")
        if bank:
            qs = qs.filter(bank=bank)
        return {
            "total_open": qs.count(),
            "critical": qs.filter(severity="critical").count(),
            "high": qs.filter(severity="high").count(),
            "medium": qs.filter(severity="medium").count(),
            "low": qs.filter(severity="low").count(),
            "avg_risk_score": round(
                (qs.aggregate(avg=Avg("risk_score"))["avg"] or 0), 3
            ),
        }
