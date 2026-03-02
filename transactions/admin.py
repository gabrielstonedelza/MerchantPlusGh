from django.contrib import admin
from django.utils.html import format_html
from .models import (
    AgentRequest, BankTransaction, MobileMoneyTransaction,
    CashTransaction, ExpenseRequest, DailyClosing,
)


class BankTransactionInline(admin.StackedInline):
    model = BankTransaction
    extra = 0


class MoMoInline(admin.StackedInline):
    model = MobileMoneyTransaction
    extra = 0


class CashInline(admin.StackedInline):
    model = CashTransaction
    extra = 0


@admin.register(AgentRequest)
class AgentRequestAdmin(admin.ModelAdmin):
    list_display = [
        "reference", "requested_by", "transaction_type", "channel", "bank", "mobile_network",
        "status", "amount", "fee", "company", "requested_at",
    ]
    list_filter = ["transaction_type", "channel", "bank", "mobile_network", "status", "company"]
    search_fields = ["reference", "customer__full_name", "customer__phone", "requested_by__full_name"]
    autocomplete_fields = ["company", "customer", "approved_by", "requested_by", "settled_by"]
    readonly_fields = ["id", "reference", "requested_at", "settled_at", "customer_accounts_display"]
    inlines = [BankTransactionInline, MoMoInline, CashInline]

    fieldsets = (
        (None, {
            "fields": (
                "id", "reference", "company", "requested_by",
                "customer", "customer_accounts_display",
            ),
        }),
        ("Transaction Details", {
            "fields": (
                "transaction_type", "channel",
                "bank", "mobile_network",
                "amount", "fee",
            ),
        }),
        ("Approval", {
            "fields": (
                "status", "requires_approval", "approved_by",
                "approved_at", "rejection_reason",
            ),
        }),
        ("Settlement", {
            "fields": ("settled_by", "settled_at"),
        }),
        ("Timestamps", {
            "fields": ("requested_at",),
        }),
    )

    @admin.display(description="Customer Accounts")
    def customer_accounts_display(self, obj):
        """Show the selected customer's registered bank and MoMo accounts."""
        if not obj.customer_id:
            return format_html(
                '<span style="color:#888;">Select a customer first to see their accounts.</span>'
            )

        accounts = obj.customer.accounts.all()
        if not accounts.exists():
            return format_html(
                '<span style="color:#e8a838;">⚠ This customer has no registered accounts. '
                'Add them via the <a href="/admin/customers/customer/{}/change/">Customer page</a>.'
                "</span>",
                obj.customer_id,
            )

        bank_accounts = [a for a in accounts if a.account_type == "bank"]
        momo_accounts = [a for a in accounts if a.account_type == "mobile_money"]

        rows = []

        if bank_accounts:
            rows.append("<strong>🏦 Bank Accounts:</strong>")
            for a in bank_accounts:
                primary = " ⭐" if a.is_primary else ""
                rows.append(
                    f"&nbsp;&nbsp;• {a.bank_or_network_display} — {a.account_number} ({a.account_name}){primary}"
                )

        if momo_accounts:
            rows.append("<strong>📱 Mobile Money Accounts:</strong>")
            for a in momo_accounts:
                primary = " ⭐" if a.is_primary else ""
                rows.append(
                    f"&nbsp;&nbsp;• {a.bank_or_network_display} — {a.account_number} ({a.account_name}){primary}"
                )

        return format_html("<br>".join(rows))


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "transaction", "get_transaction_type", "get_status",
        "bank_name", "account_number", "account_name", "customer_name",
        "get_amount",
    ]
    list_filter = ["transaction__transaction_type", "transaction__status"]
    search_fields = ["bank_name", "account_number", "account_name", "customer_name", "transaction__reference"]
    autocomplete_fields = ["transaction"]
    readonly_fields = ["get_transaction_type", "get_status", "get_amount", "get_channel"]

    @admin.display(description="Type", ordering="transaction__transaction_type")
    def get_transaction_type(self, obj):
        return obj.transaction.get_transaction_type_display()

    @admin.display(description="Status", ordering="transaction__status")
    def get_status(self, obj):
        return obj.transaction.get_status_display()

    @admin.display(description="Amount", ordering="transaction__amount")
    def get_amount(self, obj):
        return f"GHS {obj.transaction.amount}"

    @admin.display(description="Channel", ordering="transaction__channel")
    def get_channel(self, obj):
        return obj.transaction.get_channel_display()


@admin.register(MobileMoneyTransaction)
class MobileMoneyTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "transaction", "get_transaction_type", "get_status",
        "network", "service_type", "sender_number", "receiver_number",
        "momo_reference", "get_amount",
    ]
    list_filter = ["network", "service_type", "transaction__transaction_type", "transaction__status"]
    search_fields = ["sender_number", "receiver_number", "momo_reference", "transaction__reference"]
    autocomplete_fields = ["transaction"]
    readonly_fields = ["get_transaction_type", "get_status", "get_amount", "get_channel"]

    @admin.display(description="Type", ordering="transaction__transaction_type")
    def get_transaction_type(self, obj):
        return obj.transaction.get_transaction_type_display()

    @admin.display(description="Status", ordering="transaction__status")
    def get_status(self, obj):
        return obj.transaction.get_status_display()

    @admin.display(description="Amount", ordering="transaction__amount")
    def get_amount(self, obj):
        return f"GHS {obj.transaction.amount}"

    @admin.display(description="Channel", ordering="transaction__channel")
    def get_channel(self, obj):
        return obj.transaction.get_channel_display()


@admin.register(ExpenseRequest)
class ExpenseRequestAdmin(admin.ModelAdmin):
    list_display = ["requested_by", "amount", "status", "company", "created_at"]
    list_filter = ["status", "company"]
    search_fields = ["reason", "requested_by__full_name"]


@admin.register(DailyClosing)
class DailyClosingAdmin(admin.ModelAdmin):
    list_display = [
        "date", "closed_by", "company", "branch",
        "physical_cash", "total_ecash", "overage", "shortage",
    ]
    list_filter = ["company", "branch"]
    search_fields = ["closed_by__full_name"]
