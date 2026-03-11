from django.contrib import admin
from .models import FraudRule, FraudSignal, FraudAuditLog


@admin.register(FraudRule)
class FraudRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "rule_type", "severity", "bank", "is_active", "company"]
    list_filter = ["rule_type", "severity", "is_active", "company"]
    search_fields = ["name"]


@admin.register(FraudSignal)
class FraudSignalAdmin(admin.ModelAdmin):
    list_display = [
        "customer", "signal_type", "severity", "risk_score",
        "status", "triggered_at", "company",
    ]
    list_filter = ["severity", "status", "signal_type", "company"]
    search_fields = ["customer", "description"]
    readonly_fields = ["triggered_at"]


@admin.register(FraudAuditLog)
class FraudAuditLogAdmin(admin.ModelAdmin):
    list_display = ["signal", "action", "performed_by", "timestamp"]
    list_filter = ["action"]
    readonly_fields = ["timestamp"]
