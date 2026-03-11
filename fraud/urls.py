from django.urls import path
from . import views

urlpatterns = [
    # Rules
    path("rules/", views.fraud_rules, name="fraud-rules"),
    path("rules/<uuid:rule_id>/", views.fraud_rule_detail, name="fraud-rule-detail"),

    # Signals
    path("signals/", views.fraud_signals, name="fraud-signals"),
    path("signals/<uuid:signal_id>/", views.fraud_signal_detail, name="fraud-signal-detail"),
    path("signals/<uuid:signal_id>/resolve/", views.fraud_signal_resolve, name="fraud-signal-resolve"),

    # Dashboard
    path("risk-summary/", views.fraud_risk_summary, name="fraud-risk-summary"),

    # Manual scan
    path("scan/", views.fraud_manual_scan, name="fraud-manual-scan"),
]
