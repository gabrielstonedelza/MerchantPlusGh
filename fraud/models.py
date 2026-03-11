import uuid
from django.db import models
from django.utils import timezone


class FraudRule(models.Model):
    """Configurable fraud detection rules per bank or globally."""

    RULE_TYPES = [
        ("velocity", "Velocity Check"),
        ("amount_spike", "Amount Spike"),
        ("odd_hours", "Odd Hours Activity"),
        ("cross_bank", "Cross-Bank Anomaly"),
        ("dormant_account", "Dormant Account Activity"),
    ]

    SEVERITY = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "core.Company", on_delete=models.CASCADE, related_name="fraud_rules"
    )
    name = models.CharField(max_length=100)
    rule_type = models.CharField(max_length=30, choices=RULE_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY, default="medium")
    bank = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Leave blank to apply globally across all banks.",
    )
    is_active = models.BooleanField(default=True)

    # Threshold config
    threshold_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="For amount_spike: multiplier above average to flag.",
    )
    threshold_count = models.IntegerField(
        null=True, blank=True,
        help_text="For velocity/cross_bank: max count before flagging.",
    )
    threshold_window_minutes = models.IntegerField(
        default=60, help_text="Time window in minutes.",
    )
    odd_hour_start = models.IntegerField(
        default=22, help_text="Hour (0-23) fraud window starts.",
    )
    odd_hour_end = models.IntegerField(
        default=5, help_text="Hour (0-23) fraud window ends.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        scope = "Global" if not self.bank else self.bank
        return f"[{self.severity.upper()}] {self.name} ({scope})"


class FraudSignal(models.Model):
    """A flagged fraud event tied to a customer transaction."""

    STATUS = [
        ("open", "Open"),
        ("reviewing", "Under Review"),
        ("confirmed", "Confirmed Fraud"),
        ("dismissed", "Dismissed"),
        ("auto_cleared", "Auto-Cleared"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "core.Company", on_delete=models.CASCADE, related_name="fraud_signals"
    )

    # Customer identification
    customer = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, default="")
    bank = models.CharField(max_length=100, blank=True, default="")

    # Signal metadata
    rule = models.ForeignKey(
        FraudRule, on_delete=models.SET_NULL, null=True, related_name="signals",
    )
    signal_type = models.CharField(max_length=30)
    severity = models.CharField(max_length=10, default="medium")
    description = models.TextField()
    risk_score = models.FloatField(default=0.0, help_text="0.0 to 1.0")

    # Linked transaction
    related_transaction_id = models.UUIDField(null=True, blank=True)
    related_transaction_type = models.CharField(
        max_length=30, blank=True, default="",
    )

    # Evidence snapshot
    evidence = models.JSONField(default=dict)

    status = models.CharField(max_length=20, choices=STATUS, default="open")
    reviewed_by = models.CharField(max_length=100, blank=True, default="")
    review_notes = models.TextField(blank=True, default="")

    triggered_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-triggered_at"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "severity"]),
        ]

    def __str__(self):
        return f"Fraud Signal [{self.severity}] - {self.customer} @ {self.triggered_at:%Y-%m-%d %H:%M}"

    def resolve(self, status, reviewer=None, notes=None):
        self.status = status
        self.reviewed_by = reviewer or ""
        self.review_notes = notes or ""
        self.resolved_at = timezone.now()
        self.save()


class FraudAuditLog(models.Model):
    """Append-only log of all fraud review actions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signal = models.ForeignKey(
        FraudSignal, on_delete=models.CASCADE, related_name="audit_logs",
    )
    action = models.CharField(max_length=50)
    performed_by = models.CharField(max_length=100, default="system")
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} on Signal #{self.signal_id} by {self.performed_by}"
