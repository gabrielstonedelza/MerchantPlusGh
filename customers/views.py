from django.db import models
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Customer, CustomerAccount
from .serializers import (
    CustomerSerializer,
    CustomerCreateSerializer,
    CustomerUpdateSerializer,
    CustomerAccountSerializer,
    CustomerKYCSerializer,
)


# ---------------------------------------------------------------------------
# Customer CRUD
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
def customers(request):
    """List or register customers (shared across all companies)."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        qs = Customer.objects.select_related("registered_by")

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        kyc_filter = request.query_params.get("kyc_status")
        if kyc_filter:
            qs = qs.filter(kyc_status=kyc_filter)

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                models.Q(full_name__icontains=search)
                | models.Q(phone__icontains=search)
            )

        return Response(CustomerSerializer(qs, many=True).data)

    # POST - register new customer
    serializer = CustomerCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    customer = serializer.save(
        registered_by=request.user,
    )

    return Response(
        CustomerSerializer(customer).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
def customer_detail(request, customer_id):
    """Retrieve, update, or delete a customer."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(CustomerSerializer(customer).data)

    if request.method == "PATCH":
        serializer = CustomerUpdateSerializer(
            customer, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CustomerSerializer(customer).data)

    if request.method == "DELETE":
        if membership.role != "owner":
            return Response(
                {"error": "Only owners can delete customers."},
                status=status.HTTP_403_FORBIDDEN,
            )
        customer.status = Customer.Status.INACTIVE
        customer.save(update_fields=["status"])
        return Response({"message": "Customer deactivated."})


@api_view(["GET"])
def customer_by_phone(request):
    """Look up a customer by phone number."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    phone = request.query_params.get("phone")
    if not phone:
        return Response(
            {"error": "Phone parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        customer = Customer.objects.get(phone=phone)
    except Customer.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    return Response(CustomerSerializer(customer).data)


# ---------------------------------------------------------------------------
# KYC Verification
# ---------------------------------------------------------------------------
@api_view(["POST"])
def verify_kyc(request, customer_id):
    """Approve or reject a customer's KYC. Owner only."""
    membership = getattr(request, "membership", None)
    if not membership or membership.role != "owner":
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    serializer = CustomerKYCSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    customer.kyc_status = serializer.validated_data["kyc_status"]
    if customer.kyc_status == Customer.KYCStatus.VERIFIED:
        customer.kyc_verified_at = timezone.now()
        customer.kyc_verified_by = request.user
    customer.save()

    return Response(CustomerSerializer(customer).data)


# ---------------------------------------------------------------------------
# Customer Accounts
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
def customer_accounts(request, customer_id):
    """List or add accounts for a customer."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        accounts = CustomerAccount.objects.filter(customer=customer)
        return Response(CustomerAccountSerializer(accounts, many=True).data)

    serializer = CustomerAccountSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(customer=customer)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
def delete_customer_account(request, customer_id, account_id):
    """Delete a customer's bank/mobile money account."""
    membership = getattr(request, "membership", None)
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)

    try:
        account = CustomerAccount.objects.get(
            id=account_id,
            customer_id=customer_id,
        )
    except CustomerAccount.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    account.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
