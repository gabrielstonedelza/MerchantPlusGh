"""
Pytest fixtures for the Merchant+ test suite.

Provides:
  - Subscription plans (free, pro)
  - Company + owner user + membership
  - Auth tokens
  - API client
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from core.models import SubscriptionPlan, Company, CompanySettings
from accounts.models import User, Membership
from customers.models import Customer


@pytest.fixture
def free_plan(db):
    return SubscriptionPlan.objects.create(
        name="Free",
        tier="free",
        max_users=3,
        max_customers=50,
        max_transactions_per_month=100,
        has_reports=False,
        has_audit_trail=False,
        has_api_access=False,
        has_mobile_money=True,
        has_bank_deposits=True,
        has_multi_branch=False,
        monthly_price=0,
    )


@pytest.fixture
def pro_plan(db):
    return SubscriptionPlan.objects.create(
        name="Professional",
        tier="professional",
        max_users=20,
        max_customers=5000,
        max_transactions_per_month=0,
        has_reports=True,
        has_audit_trail=True,
        has_api_access=True,
        has_mobile_money=True,
        has_bank_deposits=True,
        has_multi_branch=True,
        monthly_price=Decimal("99.00"),
    )


@pytest.fixture
def company(pro_plan, db):
    return Company.objects.create(
        name="Test Company",
        slug="test-company",
        email="info@testcompany.com",
        phone="+233200000000",
        subscription_plan=pro_plan,
        subscription_status="active",
        status="active",
    )


@pytest.fixture
def company_settings(company, db):
    return CompanySettings.objects.create(
        company=company,
        require_approval_above=Decimal("1000.00"),
        deposit_fee_percentage=Decimal("1.00"),
        withdrawal_fee_percentage=Decimal("1.50"),
        transfer_fee_flat=Decimal("2.00"),
    )


@pytest.fixture
def owner_user(db):
    user = User.objects.create_user(
        email="owner@testcompany.com",
        password="securepassword123",
        full_name="Test Owner",
        phone="+233200000001",
    )
    return user


@pytest.fixture
def owner_membership(owner_user, company):
    return Membership.objects.create(
        user=owner_user,
        company=company,
        role="owner",
        is_active=True,
    )


@pytest.fixture
def agent_user(db):
    return User.objects.create_user(
        email="agent@testcompany.com",
        password="agentpass123",
        full_name="Test Agent",
        phone="+233200000002",
    )


@pytest.fixture
def agent_membership(agent_user, company):
    return Membership.objects.create(
        user=agent_user,
        company=company,
        role="agent",
        is_active=True,
    )


@pytest.fixture
def owner_token(owner_user):
    token, _ = Token.objects.get_or_create(user=owner_user)
    return token.key


@pytest.fixture
def agent_token(agent_user):
    token, _ = Token.objects.get_or_create(user=agent_user)
    return token.key


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def owner_client(owner_token, company):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token}")
    client.defaults["HTTP_X_COMPANY_ID"] = str(company.id)
    return client


@pytest.fixture
def agent_client(agent_token, company):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {agent_token}")
    client.defaults["HTTP_X_COMPANY_ID"] = str(company.id)
    return client


@pytest.fixture
def customer(company, owner_user):
    return Customer.objects.create(
        company=company,
        registered_by=owner_user,
        full_name="John Doe",
        phone="+233501234567",
        email="john@example.com",
        kyc_status="verified",
        status="active",
    )
