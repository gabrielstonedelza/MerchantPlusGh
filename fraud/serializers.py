from rest_framework import serializers
from .models import FraudRule, FraudSignal, FraudAuditLog


class FraudRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudRule
        fields = [
            "id", "name", "rule_type", "severity", "bank", "is_active",
            "threshold_amount", "threshold_count", "threshold_window_minutes",
            "odd_hour_start", "odd_hour_end", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class FraudAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudAuditLog
        fields = ["id", "action", "performed_by", "notes", "timestamp", "metadata"]


class FraudSignalSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True, default="")
    audit_logs = FraudAuditLogSerializer(many=True, read_only=True)

    class Meta:
        model = FraudSignal
        fields = [
            "id", "customer", "phone", "bank",
            "rule", "rule_name", "signal_type", "severity",
            "description", "risk_score", "status",
            "related_transaction_id", "related_transaction_type",
            "evidence", "triggered_at", "resolved_at",
            "reviewed_by", "review_notes", "audit_logs",
        ]
        read_only_fields = ["id", "triggered_at", "rule_name", "audit_logs"]


class FraudSignalResolveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["reviewing", "confirmed", "dismissed", "auto_cleared"]
    )
    review_notes = serializers.CharField(required=False, allow_blank=True, default="")


class FraudRiskSummarySerializer(serializers.Serializer):
    total_open = serializers.IntegerField()
    critical = serializers.IntegerField()
    high = serializers.IntegerField()
    medium = serializers.IntegerField()
    low = serializers.IntegerField()
    avg_risk_score = serializers.FloatField()
