"""
Tests for agent request creation and approval workflow.
"""

import pytest
from decimal import Decimal
from rest_framework import status

from transactions.models import AgentRequest


@pytest.mark.django_db
class TestCreateAgentRequests:
    def test_create_bank_deposit(self, owner_client, owner_membership, company_settings, customer):
        response = owner_client.post("/api/v1/transactions/bank-deposit/", {
            "customer": str(customer.id),
            "amount": "500.00",
            "bank_name": "Ecobank",
            "account_number": "1234567890",
            "account_name": "John Doe",
            "depositor_name": "John Doe",
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["transaction_type"] == "deposit"
        assert response.data["channel"] == "bank"
        # All new requests start as pending regardless of amount
        assert response.data["status"] == "pending"
        assert response.data["requires_approval"] is True
        # Fee should be 1% of 500 = 5.00
        assert Decimal(response.data["fee"]) == Decimal("5.00")

    def test_large_deposit_also_starts_pending(self, owner_client, owner_membership, company_settings, customer):
        response = owner_client.post("/api/v1/transactions/bank-deposit/", {
            "customer": str(customer.id),
            "amount": "5000.00",
            "bank_name": "GCB",
            "account_number": "9876543210",
            "account_name": "John Doe",
            "depositor_name": "John Doe",
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "pending"
        assert response.data["requires_approval"] is True

    def test_create_cash_transaction(self, owner_client, owner_membership, company_settings, customer):
        response = owner_client.post("/api/v1/transactions/cash/", {
            "customer": str(customer.id),
            "transaction_type": "deposit",
            "amount": "200.00",
            "d_100": 2,
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["channel"] == "cash"
        assert response.data["status"] == "pending"

    def test_create_momo_transaction(self, owner_client, owner_membership, company_settings, customer):
        response = owner_client.post("/api/v1/transactions/mobile-money/", {
            "customer": str(customer.id),
            "transaction_type": "deposit",
            "amount": "100.00",
            "network": "mtn",
            "service_type": "cash_in",
            "sender_number": "+233501234567",
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["channel"] == "mobile_money"
        assert response.data["status"] == "pending"


@pytest.mark.django_db
class TestApprovalWorkflow:
    def test_approve_request(
        self, owner_client, agent_client, owner_membership, agent_membership, company_settings, customer
    ):
        # Agent creates a request
        create_resp = agent_client.post("/api/v1/transactions/bank-deposit/", {
            "customer": str(customer.id),
            "amount": "5000.00",
            "bank_name": "Ecobank",
            "account_number": "1234567890",
            "account_name": "John Doe",
            "depositor_name": "John Doe",
        })
        assert create_resp.status_code == status.HTTP_201_CREATED
        req_id = create_resp.data["id"]

        # Owner approves it
        approve_resp = owner_client.post(f"/api/v1/transactions/{req_id}/approve/", {
            "action": "approve",
        })
        assert approve_resp.status_code == status.HTTP_200_OK
        assert approve_resp.data["status"] == "approved"

    def test_reject_request(
        self, owner_client, agent_client, owner_membership, agent_membership, company_settings, customer
    ):
        create_resp = agent_client.post("/api/v1/transactions/bank-deposit/", {
            "customer": str(customer.id),
            "amount": "2000.00",
            "bank_name": "GCB",
            "account_number": "1234567890",
            "account_name": "Jane Doe",
            "depositor_name": "Jane Doe",
        })
        req_id = create_resp.data["id"]

        reject_resp = owner_client.post(f"/api/v1/transactions/{req_id}/approve/", {
            "action": "reject",
            "rejection_reason": "Incomplete documentation",
        })
        assert reject_resp.status_code == status.HTTP_200_OK
        assert reject_resp.data["status"] == "rejected"

    def test_agent_cannot_approve(
        self, owner_client, agent_client, owner_membership, agent_membership, company_settings, customer
    ):
        create_resp = owner_client.post("/api/v1/transactions/bank-deposit/", {
            "customer": str(customer.id),
            "amount": "5000.00",
            "bank_name": "GCB",
            "account_number": "1234567890",
            "account_name": "Test",
            "depositor_name": "Test",
        })
        req_id = create_resp.data["id"]

        approve_resp = agent_client.post(f"/api/v1/transactions/{req_id}/approve/", {
            "action": "approve",
        })
        assert approve_resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestRequestList:
    def test_owner_sees_all_requests(
        self, owner_client, agent_client, owner_membership, agent_membership, company_settings, customer
    ):
        # Agent creates 2 requests
        for _ in range(2):
            agent_client.post("/api/v1/transactions/cash/", {
                "customer": str(customer.id),
                "transaction_type": "deposit",
                "amount": "100.00",
            })

        response = owner_client.get("/api/v1/transactions/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_agent_sees_all_company_requests(
        self, owner_client, agent_client, owner_membership, agent_membership, company_settings, customer
    ):
        # Owner creates 1 request
        owner_client.post("/api/v1/transactions/cash/", {
            "customer": str(customer.id),
            "transaction_type": "deposit",
            "amount": "100.00",
        })
        # Agent creates 1 request
        agent_client.post("/api/v1/transactions/cash/", {
            "customer": str(customer.id),
            "transaction_type": "deposit",
            "amount": "100.00",
        })

        # Both agents and owners see all company requests
        response = agent_client.get("/api/v1/transactions/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_pending_approvals_list(
        self, owner_client, agent_client, owner_membership, agent_membership, company_settings, customer
    ):
        agent_client.post("/api/v1/transactions/cash/", {
            "customer": str(customer.id),
            "transaction_type": "deposit",
            "amount": "300.00",
        })

        response = owner_client.get("/api/v1/transactions/pending/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        for item in response.data:
            assert item["status"] == "pending"
