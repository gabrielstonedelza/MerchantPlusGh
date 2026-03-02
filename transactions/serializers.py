from rest_framework import serializers
from .models import (
    AgentRequest, BankTransaction, MobileMoneyTransaction,
    CashTransaction, ExpenseRequest, DailyClosing, ProviderBalance,
)


class BankTransactionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankTransaction
        fields = [
            "bank_name", "account_number", "account_name",
            "customer_name",
        ]


class MoMoDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobileMoneyTransaction
        fields = [
            "network", "service_type",
            "sender_number", "receiver_number", "momo_reference",
        ]


class CashDetailSerializer(serializers.ModelSerializer):
    denomination_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = CashTransaction
        fields = [
            "d_200", "d_100", "d_50", "d_20", "d_10", "d_5", "d_2", "d_1",
            "denomination_total",
        ]


class AgentRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(
        source="requested_by.full_name", read_only=True, default=None
    )
    approved_by_name = serializers.CharField(
        source="approved_by.full_name", read_only=True, default=None
    )
    settled_by_name = serializers.CharField(
        source="settled_by.full_name", read_only=True, default=None
    )
    customer_name = serializers.CharField(
        source="customer.full_name", read_only=True, default=None
    )
    customer_phone = serializers.CharField(
        source="customer.phone", read_only=True, default=None
    )
    bank_display = serializers.CharField(
        source="get_bank_display", read_only=True, default=""
    )
    mobile_network_display = serializers.CharField(
        source="get_mobile_network_display", read_only=True, default=""
    )
    bank_transaction_detail = BankTransactionDetailSerializer(read_only=True)
    momo_detail = MoMoDetailSerializer(read_only=True)
    cash_detail = CashDetailSerializer(read_only=True)

    class Meta:
        model = AgentRequest
        fields = [
            "id", "reference", "company",
            "requested_by", "requested_by_name",
            "customer", "customer_name", "customer_phone",
            "transaction_type", "channel",
            "bank", "bank_display", "mobile_network", "mobile_network_display",
            "status",
            "amount", "fee",
            "requires_approval", "approved_by", "approved_by_name",
            "approved_at", "rejection_reason",
            "settled_by", "settled_by_name", "settled_at",
            "bank_transaction_detail", "momo_detail", "cash_detail",
            "requested_at",
        ]
        read_only_fields = [
            "id", "reference", "company",
            "requested_by",
            "fee",
            "requires_approval", "approved_by", "approved_at",
            "settled_by", "settled_at",
            "requested_at",
        ]


# Alias so existing imports in other apps don't break
TransactionSerializer = AgentRequestSerializer


class CreateBankTransactionSerializer(serializers.Serializer):
    customer = serializers.UUIDField(required=False, allow_null=True)
    transaction_type = serializers.ChoiceField(
        choices=[("deposit", "Deposit"), ("withdrawal", "Withdrawal")]
    )
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    bank = serializers.ChoiceField(
        choices=AgentRequest.Bank.choices, required=False, allow_blank=True,
    )
    bank_name = serializers.CharField(max_length=100)
    account_number = serializers.CharField(max_length=50)
    account_name = serializers.CharField(max_length=255)
    customer_name = serializers.CharField(max_length=255)


class CreateMoMoTransactionSerializer(serializers.Serializer):
    customer = serializers.UUIDField(required=False, allow_null=True)
    transaction_type = serializers.ChoiceField(
        choices=[("deposit", "Deposit"), ("withdrawal", "Withdrawal")]
    )
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    network = serializers.ChoiceField(choices=MobileMoneyTransaction.Network.choices)
    service_type = serializers.ChoiceField(
        choices=MobileMoneyTransaction.ServiceType.choices
    )
    sender_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    receiver_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    momo_reference = serializers.CharField(max_length=50, required=False, allow_blank=True)


class CreateCashTransactionSerializer(serializers.Serializer):
    customer = serializers.UUIDField(required=False, allow_null=True)
    transaction_type = serializers.ChoiceField(
        choices=[("deposit", "Deposit"), ("withdrawal", "Withdrawal")]
    )
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    d_200 = serializers.IntegerField(default=0)
    d_100 = serializers.IntegerField(default=0)
    d_50 = serializers.IntegerField(default=0)
    d_20 = serializers.IntegerField(default=0)
    d_10 = serializers.IntegerField(default=0)
    d_5 = serializers.IntegerField(default=0)
    d_2 = serializers.IntegerField(default=0)
    d_1 = serializers.IntegerField(default=0)


class ApproveTransactionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[("approve", "Approve"), ("reject", "Reject")])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


class ExpenseRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(
        source="requested_by.full_name", read_only=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.full_name", read_only=True, default=None
    )

    class Meta:
        model = ExpenseRequest
        fields = [
            "id", "company",
            "requested_by", "requested_by_name",
            "amount", "reason", "status",
            "approved_by", "approved_by_name", "approved_at",
            "rejection_reason", "receipt_image",
            "created_at",
        ]
        read_only_fields = [
            "id", "company", "requested_by", "status",
            "approved_by", "approved_at", "created_at",
        ]


class ExpenseRequestCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField()
    receipt_image = serializers.ImageField(required=False)


class DailyClosingSerializer(serializers.ModelSerializer):
    closed_by_name = serializers.CharField(
        source="closed_by.full_name", read_only=True
    )
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, default=None
    )

    class Meta:
        model = DailyClosing
        fields = [
            "id", "company", "branch", "branch_name",
            "closed_by", "closed_by_name", "date",
            "physical_cash", "mtn_ecash", "vodafone_ecash",
            "airteltigo_ecash", "total_ecash",
            "overage", "shortage", "notes",
            "created_at",
        ]
        read_only_fields = ["id", "company", "closed_by", "created_at"]


class ProviderBalanceSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    provider_display = serializers.CharField(
        source="get_provider_display", read_only=True
    )

    class Meta:
        model = ProviderBalance
        fields = [
            "id", "company", "user", "user_name",
            "provider", "provider_display",
            "starting_balance", "balance",
            "last_updated", "created_at",
        ]
        read_only_fields = ["id", "company", "last_updated", "created_at"]


class SetProviderBalanceSerializer(serializers.Serializer):
    """Used by admins to set starting balances for a user."""
    user = serializers.UUIDField()
    provider = serializers.ChoiceField(choices=ProviderBalance.Provider.choices)
    starting_balance = serializers.DecimalField(max_digits=14, decimal_places=2)


class AdjustProviderBalanceSerializer(serializers.Serializer):
    """Used to adjust a provider balance (deposit adds, withdrawal subtracts)."""
    provider = serializers.ChoiceField(choices=ProviderBalance.Provider.choices)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    operation = serializers.ChoiceField(choices=[("add", "Add"), ("subtract", "Subtract")])


class AdminAdjustProviderBalanceSerializer(serializers.Serializer):
    """Used by admin/owner to directly set or adjust any agent's balance."""
    user = serializers.UUIDField()
    provider = serializers.ChoiceField(choices=ProviderBalance.Provider.choices)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    operation = serializers.ChoiceField(choices=[("add", "Add"), ("subtract", "Subtract"), ("set", "Set")])
    note = serializers.CharField(required=False, allow_blank=True)
