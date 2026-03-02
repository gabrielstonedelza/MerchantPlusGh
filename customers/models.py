import uuid
from django.db import models

from .encryption import encrypt_uploaded_file


class Customer(models.Model):
    """
    A customer shared across the entire MerchantPlus platform.
    Any company can register a new customer and they can transact with any company.
    Phone numbers, full names, and emails are unique across all customers.
    Photos are encrypted at rest for security.
    """

    class KYCStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        BLOCKED = "blocked", "Blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registered_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="registered_customers",
    )

    # Personal info — phone, full_name, and email are globally unique
    full_name = models.CharField(max_length=255, unique=True)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    digital_address = models.CharField(max_length=50, blank=True)
    photo = models.FileField(upload_to="customer_photos/", blank=True, null=True)

    # Identification (KYC)
    id_type = models.CharField(
        max_length=30,
        choices=[
            ("passport", "Passport"),
            ("national_id", "National ID / Ghana Card"),
            ("drivers_license", "Driver's License"),
            ("voter_id", "Voter ID"),
        ],
        blank=True,
    )
    id_number = models.CharField(max_length=50, blank=True)
    id_document_front = models.FileField(
        upload_to="customer_ids/", blank=True, null=True
    )
    id_document_back = models.FileField(
        upload_to="customer_ids/", blank=True, null=True
    )
    kyc_status = models.CharField(
        max_length=20, choices=KYCStatus.choices, default=KYCStatus.PENDING
    )
    kyc_verified_at = models.DateTimeField(null=True, blank=True)
    kyc_verified_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_customers",
    )

    # Status
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )

    # Loyalty
    loyalty_points = models.PositiveIntegerField(default=0)

    # Referral
    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    def save(self, *args, **kwargs):
        """Encrypt photo and ID document files before saving."""
        for field_name in ("photo", "id_document_front", "id_document_back"):
            field = getattr(self, field_name)
            if not field:
                continue
            # Skip files already encrypted (saved to disk with .enc extension)
            if field.name and field.name.endswith(".enc"):
                continue
            # Only encrypt genuinely new uploads
            if hasattr(field, "file") and hasattr(field.file, "read"):
                encrypted = encrypt_uploaded_file(field.file)
                if encrypted:
                    setattr(self, field_name, encrypted)

        super().save(*args, **kwargs)


class CustomerAccount(models.Model):
    """Bank or mobile money accounts belonging to a customer."""

    class AccountType(models.TextChoices):
        BANK = "bank", "Bank Account"
        MOBILE_MONEY = "mobile_money", "Mobile Money"

    # Re-use the same choice lists defined on AgentRequest
    class Bank(models.TextChoices):
        ECOBANK = "ecobank", "Ecobank"
        GCB = "gcb", "GCB Bank"
        FIDELITY = "fidelity", "Fidelity Bank"
        CAL_BANK = "cal_bank", "Cal Bank"
        STANBIC = "stanbic", "Stanbic Bank"
        ABSA = "absa", "Absa Bank"
        UBA = "uba", "UBA"
        ACCESS = "access", "Access Bank"
        ZENITH = "zenith", "Zenith Bank"
        REPUBLIC = "republic", "Republic Bank"
        PRUDENTIAL = "prudential", "Prudential Bank"
        FNB = "fnb", "First National Bank"
        STANDARD_CHARTERED = "standard_chartered", "Standard Chartered"
        SOCIETE_GENERALE = "societe_generale", "Societe Generale"
        BOA = "boa", "Bank of Africa"
        ADB = "adb", "Agricultural Dev Bank"
        FAB = "fab", "First Atlantic Bank"
        OMNIBSIC = "omnibsic", "OmniBSIC Bank"
        NIB = "nib", "National Investment Bank"
        ARB_APEX = "arb_apex", "ARB Apex Bank"

    class MobileNetwork(models.TextChoices):
        MTN = "mtn", "MTN"
        VODAFONE = "vodafone", "Vodafone"
        AIRTELTIGO = "airteltigo", "AirtelTigo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="accounts"
    )

    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    account_number = models.CharField(max_length=50)
    account_name = models.CharField(max_length=255)
    bank = models.CharField(
        max_length=30,
        choices=Bank.choices,
        blank=True,
        default="",
        help_text="Select the bank (only when account type is Bank).",
    )
    mobile_network = models.CharField(
        max_length=20,
        choices=MobileNetwork.choices,
        blank=True,
        default="",
        help_text="Select the network (only when account type is Mobile Money).",
    )
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "-created_at"]

    @property
    def bank_or_network_display(self):
        """Human-readable name of the bank or network."""
        if self.account_type == self.AccountType.BANK and self.bank:
            return self.get_bank_display()
        if self.account_type == self.AccountType.MOBILE_MONEY and self.mobile_network:
            return self.get_mobile_network_display()
        return ""

    def __str__(self):
        return f"{self.account_name} - {self.bank_or_network_display} ({self.account_number})"
