from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils import timezone
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    AgentRequest, BankTransaction, MobileMoneyTransaction,
    CashTransaction, ExpenseRequest, DailyClosing, ProviderBalance,
)
from .serializers import (
    AgentRequestSerializer,
    CreateBankTransactionSerializer,
    CreateMoMoTransactionSerializer,
    CreateCashTransactionSerializer,
    ApproveTransactionSerializer,
    ExpenseRequestSerializer,
    ExpenseRequestCreateSerializer,
    DailyClosingSerializer,
    ProviderBalanceSerializer,
    SetProviderBalanceSerializer,
    AdjustProviderBalanceSerializer,
    AdminAdjustProviderBalanceSerializer,
)


def _calculate_fee(company, transaction_type, amount):
    settings = getattr(company, "settings", None)
    if not settings:
        return Decimal("0")
    if transaction_type == "deposit":
        return (settings.deposit_fee_percentage / 100) * amount
    elif transaction_type == "withdrawal":
        return (settings.withdrawal_fee_percentage / 100) * amount
    elif transaction_type == "transfer":
        return settings.transfer_fee_flat
    return Decimal("0")


# ---------------------------------------------------------------------------
# Agent Request List
# ---------------------------------------------------------------------------
@api_view(["GET"])
def transactions(request):
    """List agent requests. Supports filtering by status, type, channel, customer, date range."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    qs = AgentRequest.objects.filter(
        company=membership.company
    ).select_related(
        "requested_by", "approved_by", "settled_by", "customer",
        "bank_transaction_detail", "momo_detail", "cash_detail",
    )

    tx_status = request.query_params.get("status")
    if tx_status:
        qs = qs.filter(status=tx_status)

    tx_type = request.query_params.get("type")
    if tx_type:
        qs = qs.filter(transaction_type=tx_type)

    channel = request.query_params.get("channel")
    if channel:
        qs = qs.filter(channel=channel)

    customer_id = request.query_params.get("customer")
    if customer_id:
        qs = qs.filter(customer_id=customer_id)

    date_from = request.query_params.get("date_from")
    if date_from:
        qs = qs.filter(requested_at__date__gte=date_from)

    date_to = request.query_params.get("date_to")
    if date_to:
        qs = qs.filter(requested_at__date__lte=date_to)

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(
            Q(reference__icontains=search)
            | Q(customer__full_name__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(requested_by__full_name__icontains=search)
            | Q(transaction_type__icontains=search)
            | Q(channel__icontains=search)
        )

    return Response(AgentRequestSerializer(qs[:200], many=True).data)


@api_view(["GET"])
def transaction_detail(request, transaction_id):
    """Get a single agent request with full details."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        req = AgentRequest.objects.select_related(
            "requested_by", "approved_by", "customer",
            "bank_transaction_detail", "momo_detail", "cash_detail",
        ).get(id=transaction_id, company=membership.company)
    except AgentRequest.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    return Response(AgentRequestSerializer(req).data)


# ---------------------------------------------------------------------------
# Create Agent Requests
# ---------------------------------------------------------------------------
@api_view(["POST"])
def create_bank_transaction(request):
    """Submit a bank transaction request (deposit or withdrawal). Always starts as pending."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    serializer = CreateBankTransactionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    company = membership.company
    tx_type = data["transaction_type"]
    amount = Decimal(str(data["amount"]))
    fee = _calculate_fee(company, tx_type, amount)

    req = AgentRequest.objects.create(
        company=company,
        requested_by=request.user,
        customer_id=data.get("customer"),
        transaction_type=tx_type,
        channel=AgentRequest.Channel.BANK,
        bank=data.get("bank", ""),
        status=AgentRequest.Status.PENDING,
        amount=amount,
        fee=fee,
        requires_approval=True,
    )
    BankTransaction.objects.create(
        transaction=req,
        bank_name=data["bank_name"],
        account_number=data["account_number"],
        account_name=data["account_name"],
        customer_name=data["customer_name"],
    )
    return Response(AgentRequestSerializer(req).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def create_momo_transaction(request):
    """Submit a mobile money request. Always starts as pending for admin approval."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    if not membership.company.subscription_plan.has_mobile_money:
        return Response(
            {"error": "Mobile money is not available on your plan."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = CreateMoMoTransactionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    company = membership.company
    tx_type = data["transaction_type"]
    amount = Decimal(str(data["amount"]))
    fee = _calculate_fee(company, tx_type, amount)

    req = AgentRequest.objects.create(
        company=company,
        requested_by=request.user,
        customer_id=data.get("customer"),
        transaction_type=tx_type,
        channel=AgentRequest.Channel.MOBILE_MONEY,
        mobile_network=data["network"],
        status=AgentRequest.Status.PENDING,
        amount=amount,
        fee=fee,
        requires_approval=True,
    )
    MobileMoneyTransaction.objects.create(
        transaction=req,
        network=data["network"],
        service_type=data["service_type"],
        sender_number=data.get("sender_number", ""),
        receiver_number=data.get("receiver_number", ""),
        momo_reference=data.get("momo_reference", ""),
    )
    return Response(AgentRequestSerializer(req).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def create_cash_transaction(request):
    """Submit a cash request. Always starts as pending for admin approval."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    serializer = CreateCashTransactionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    company = membership.company
    tx_type = data["transaction_type"]
    amount = Decimal(str(data["amount"]))
    fee = _calculate_fee(company, tx_type, amount)

    req = AgentRequest.objects.create(
        company=company,
        requested_by=request.user,
        customer_id=data.get("customer"),
        transaction_type=tx_type,
        channel=AgentRequest.Channel.CASH,
        status=AgentRequest.Status.PENDING,
        amount=amount,
        fee=fee,
        requires_approval=True,
    )
    CashTransaction.objects.create(
        transaction=req,
        d_200=data.get("d_200", 0), d_100=data.get("d_100", 0),
        d_50=data.get("d_50", 0), d_20=data.get("d_20", 0),
        d_10=data.get("d_10", 0), d_5=data.get("d_5", 0),
        d_2=data.get("d_2", 0), d_1=data.get("d_1", 0),
    )
    return Response(AgentRequestSerializer(req).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Approval Workflow
# ---------------------------------------------------------------------------
@api_view(["GET"])
def pending_approvals(request):
    """List agent requests pending approval. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    qs = AgentRequest.objects.filter(
        company=membership.company,
        status=AgentRequest.Status.PENDING,
    ).select_related(
        "requested_by", "approved_by", "settled_by", "customer",
        "bank_transaction_detail", "momo_detail", "cash_detail",
    )
    return Response(AgentRequestSerializer(qs, many=True).data)


@api_view(["POST"])
def approve_transaction(request, transaction_id):
    """Approve or reject a pending agent request. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        req = AgentRequest.objects.get(
            id=transaction_id, company=membership.company,
            status=AgentRequest.Status.PENDING,
        )
    except AgentRequest.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    serializer = ApproveTransactionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    action = serializer.validated_data["action"]

    if action == "approve":
        req.status = AgentRequest.Status.APPROVED
    else:
        req.status = AgentRequest.Status.REJECTED
        req.rejection_reason = serializer.validated_data.get("rejection_reason", "")

    req.approved_by = request.user
    req.approved_at = timezone.now()
    req.save()
    return Response(AgentRequestSerializer(req).data)


# ---------------------------------------------------------------------------
# Settlement — agent executes an approved request
# ---------------------------------------------------------------------------
def _resolve_provider_key(req):
    """Map an AgentRequest's channel to the ProviderBalance provider key."""
    if req.channel == "bank":
        return req.bank if req.bank else None
    elif req.channel == "mobile_money":
        return req.mobile_network if req.mobile_network else None
    return None


@api_view(["GET"])
def pending_settlements(request):
    """List approved requests awaiting settlement by the current agent."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    qs = AgentRequest.objects.filter(
        company=membership.company,
        requested_by=request.user,
        status=AgentRequest.Status.APPROVED,
    ).select_related(
        "requested_by", "approved_by", "settled_by", "customer",
        "bank_transaction_detail", "momo_detail", "cash_detail",
    )
    return Response(AgentRequestSerializer(qs, many=True).data)


@api_view(["POST"])
def settle_request(request, transaction_id):
    """
    Settle (execute) an approved agent request.

    Called by the agent from the mobile app after admin approval.
    Adjusts the agent's provider balances atomically:

    DEPOSIT:  Cash += amount,  Bank/Network -= amount
    WITHDRAWAL: Cash -= amount, Bank/Network += amount

    The total morning float stays the same.
    """
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    with db_transaction.atomic():
        try:
            req = AgentRequest.objects.select_for_update().get(
                id=transaction_id,
                company=membership.company,
                status=AgentRequest.Status.APPROVED,
            )
        except AgentRequest.DoesNotExist:
            return Response(
                {"error": "Request not found or not in approved status."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Only the agent who created the request (or an admin) can settle
        if req.requested_by_id != request.user.id and membership.role != "owner":
            return Response(
                {"error": "Only the requesting agent can settle this request."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Determine the provider key for the bank/network side
        provider_key = _resolve_provider_key(req)
        if not provider_key:
            return Response(
                {"error": "Cannot determine provider for this request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only deposits and withdrawals can be settled
        if req.transaction_type not in ("deposit", "withdrawal"):
            return Response(
                {"error": "Only deposit and withdrawal requests can be settled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get agent's cash balance
        try:
            cash_balance = ProviderBalance.objects.select_for_update().get(
                company=membership.company,
                user=request.user,
                provider="cash",
            )
        except ProviderBalance.DoesNotExist:
            return Response(
                {"error": "No cash balance record found. Contact your admin to initialize your float."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get agent's provider balance (bank or network)
        try:
            provider_balance = ProviderBalance.objects.select_for_update().get(
                company=membership.company,
                user=request.user,
                provider=provider_key,
            )
        except ProviderBalance.DoesNotExist:
            return Response(
                {"error": f"No balance record for '{provider_key}'. Contact your admin to initialize your float."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = req.amount

        if req.transaction_type == "deposit":
            # Agent receives cash from customer, sends e-cash to customer's account
            if provider_balance.balance < amount:
                return Response(
                    {"error": f"Insufficient {provider_balance.get_provider_display()} balance. "
                              f"Available: {provider_balance.balance}, Required: {amount}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cash_balance.balance += amount
            provider_balance.balance -= amount

        elif req.transaction_type == "withdrawal":
            # Agent gives cash to customer, receives e-cash from customer
            if cash_balance.balance < amount:
                return Response(
                    {"error": f"Insufficient cash balance. "
                              f"Available: {cash_balance.balance}, Required: {amount}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cash_balance.balance -= amount
            provider_balance.balance += amount

        # Save balances (triggers WebSocket broadcasts via post_save signals)
        cash_balance.save()
        provider_balance.save()

        # Mark request as completed
        req.status = AgentRequest.Status.COMPLETED
        req.settled_by = request.user
        req.settled_at = timezone.now()
        req.save()

    # Re-fetch with select_related for serialization
    req = AgentRequest.objects.select_related(
        "requested_by", "approved_by", "settled_by", "customer",
        "bank_transaction_detail", "momo_detail", "cash_detail",
    ).get(id=transaction_id)

    return Response(AgentRequestSerializer(req).data)


# ---------------------------------------------------------------------------
# Expense Requests
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
def expense_requests(request):
    """List or create expense requests."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        qs = ExpenseRequest.objects.filter(company=membership.company)
        if membership.role == "agent":
            qs = qs.filter(requested_by=request.user)
        return Response(ExpenseRequestSerializer(qs, many=True).data)

    serializer = ExpenseRequestCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    expense = ExpenseRequest.objects.create(
        company=membership.company, requested_by=request.user,
        amount=serializer.validated_data["amount"],
        reason=serializer.validated_data["reason"],
        receipt_image=serializer.validated_data.get("receipt_image"),
    )
    return Response(ExpenseRequestSerializer(expense).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def approve_expense(request, expense_id):
    """Approve or reject an expense. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        expense = ExpenseRequest.objects.get(
            id=expense_id, company=membership.company,
            status=ExpenseRequest.Status.PENDING,
        )
    except ExpenseRequest.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    action = request.data.get("action")
    if action == "approve":
        expense.status = ExpenseRequest.Status.APPROVED
    elif action == "reject":
        expense.status = ExpenseRequest.Status.REJECTED
        expense.rejection_reason = request.data.get("rejection_reason", "")
    else:
        return Response(
            {"error": "Action must be 'approve' or 'reject'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    expense.approved_by = request.user
    expense.approved_at = timezone.now()
    expense.save()
    return Response(ExpenseRequestSerializer(expense).data)


# ---------------------------------------------------------------------------
# Daily Closing
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
def daily_closings(request):
    """List or create daily closings."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        qs = DailyClosing.objects.filter(company=membership.company)
        if membership.role == "agent":
            qs = qs.filter(closed_by=request.user)
        date_filter = request.query_params.get("date")
        if date_filter:
            qs = qs.filter(date=date_filter)
        return Response(DailyClosingSerializer(qs, many=True).data)

    serializer = DailyClosingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(
        company=membership.company, closed_by=request.user,
        branch=membership.branch,
    )
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
def daily_closing_detail(request, closing_id):
    """Get or update a daily closing."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        closing = DailyClosing.objects.get(id=closing_id, company=membership.company)
    except DailyClosing.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(DailyClosingSerializer(closing).data)

    if closing.closed_by != request.user and membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    serializer = DailyClosingSerializer(closing, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Provider Balances
# ---------------------------------------------------------------------------
@api_view(["GET"])
def provider_balances(request):
    """List all provider balances for the company. Admin+ can see all users."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    qs = ProviderBalance.objects.filter(
        company=membership.company
    ).select_related("user")

    if membership.role != "owner":
        qs = qs.filter(user=request.user)

    user_filter = request.query_params.get("user")
    if user_filter:
        qs = qs.filter(user_id=user_filter)

    provider_filter = request.query_params.get("provider")
    if provider_filter:
        qs = qs.filter(provider=provider_filter)

    return Response(ProviderBalanceSerializer(qs, many=True).data)


@api_view(["POST"])
def set_provider_balance(request):
    """Set starting balance for a user's provider. Admin+ only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    serializer = SetProviderBalanceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    balance, created = ProviderBalance.objects.update_or_create(
        company=membership.company,
        user_id=data["user"],
        provider=data["provider"],
        defaults={
            "starting_balance": data["starting_balance"],
            "balance": data["starting_balance"],
        },
    )
    return Response(
        ProviderBalanceSerializer(balance).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
def initialize_all_balances(request):
    """
    Set starting balances for ALL providers at once for a user. Admin+ only.
    Expects: { "user": "<uuid>", "balances": { "mtn": 1000, "vodafone": 500, ... } }
    """
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    user_id = request.data.get("user")
    balances = request.data.get("balances", {})
    if not user_id or not balances:
        return Response(
            {"error": "Provide 'user' and 'balances' fields."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    valid_providers = dict(ProviderBalance.Provider.choices)
    results = []
    for provider, amount in balances.items():
        if provider not in valid_providers:
            continue
        balance, _ = ProviderBalance.objects.update_or_create(
            company=membership.company,
            user_id=user_id,
            provider=provider,
            defaults={
                "starting_balance": Decimal(str(amount)),
                "balance": Decimal(str(amount)),
            },
        )
        results.append(balance)

    return Response(ProviderBalanceSerializer(results, many=True).data)


@api_view(["POST"])
def adjust_provider_balance(request):
    """Adjust a provider balance (add or subtract). Used when processing requests."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    serializer = AdjustProviderBalanceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        balance = ProviderBalance.objects.get(
            company=membership.company,
            user=request.user,
            provider=data["provider"],
        )
    except ProviderBalance.DoesNotExist:
        return Response(
            {"error": f"No balance record found for provider '{data['provider']}'."},
            status=status.HTTP_404_NOT_FOUND,
        )

    amount = data["amount"]
    if data["operation"] == "add":
        balance.balance += amount
    else:
        if balance.balance < amount:
            return Response(
                {"error": "Insufficient balance."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        balance.balance -= amount

    balance.save()
    return Response(ProviderBalanceSerializer(balance).data)


@api_view(["POST"])
def admin_adjust_provider_balance(request):
    """Admin/owner can set or adjust any agent's balance for any provider."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    serializer = AdminAdjustProviderBalanceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    amount = data["amount"]
    operation = data["operation"]

    balance, created = ProviderBalance.objects.get_or_create(
        company=membership.company,
        user_id=data["user"],
        provider=data["provider"],
        defaults={"starting_balance": amount, "balance": amount},
    )

    if not created:
        if operation == "set":
            balance.starting_balance = amount
            balance.balance = amount
        elif operation == "add":
            balance.balance += amount
        else:  # subtract
            if balance.balance < amount:
                return Response(
                    {"error": "Insufficient balance."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            balance.balance -= amount
        balance.save()

    return Response(
        ProviderBalanceSerializer(balance).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )
