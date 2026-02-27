from rest_framework import serializers
from .models import Customer, CustomerAccount
from .encryption import decrypt_photo_to_base64


class CustomerSerializer(serializers.ModelSerializer):
    registered_by_name = serializers.CharField(
        source="registered_by.full_name", read_only=True
    )
    account_count = serializers.SerializerMethodField()
    transaction_count = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id", "registered_by", "registered_by_name",
            "full_name", "phone", "email", "date_of_birth",
            "address", "city", "digital_address", "photo", "photo_url",
            "id_type", "id_number", "id_document_front", "id_document_back",
            "kyc_status", "kyc_verified_at",
            "status", "loyalty_points",
            "referred_by",
            "account_count", "transaction_count",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "registered_by",
            "kyc_status", "kyc_verified_at",
            "loyalty_points", "created_at", "updated_at",
        ]

    def get_account_count(self, obj):
        return obj.accounts.count()

    def get_transaction_count(self, obj):
        return obj.agent_requests.count() if hasattr(obj, "agent_requests") else 0

    def get_photo_url(self, obj):
        """Decrypt the encrypted photo and return as base64 data URI."""
        return decrypt_photo_to_base64(obj.photo)


class CustomerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "full_name", "phone", "email", "date_of_birth",
            "address", "city", "digital_address", "photo",
            "id_type", "id_number", "id_document_front", "id_document_back",
            "referred_by",
        ]

    def validate_phone(self, value):
        if Customer.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "A customer with this phone number already exists."
            )
        return value

    def validate_email(self, value):
        if value and Customer.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A customer with this email already exists."
            )
        return value

    def validate_full_name(self, value):
        if Customer.objects.filter(full_name=value).exists():
            raise serializers.ValidationError(
                "A customer with this name already exists."
            )
        return value


class CustomerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "full_name", "phone", "email", "date_of_birth",
            "address", "city", "digital_address", "photo",
            "id_type", "id_number", "id_document_front", "id_document_back",
            "status",
        ]

    def validate_phone(self, value):
        instance = self.instance
        if Customer.objects.filter(phone=value).exclude(pk=instance.pk).exists():
            raise serializers.ValidationError(
                "A customer with this phone number already exists."
            )
        return value

    def validate_email(self, value):
        instance = self.instance
        if value and Customer.objects.filter(email=value).exclude(pk=instance.pk).exists():
            raise serializers.ValidationError(
                "A customer with this email already exists."
            )
        return value

    def validate_full_name(self, value):
        instance = self.instance
        if Customer.objects.filter(full_name=value).exclude(pk=instance.pk).exists():
            raise serializers.ValidationError(
                "A customer with this name already exists."
            )
        return value


class CustomerAccountSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source="customer.full_name", read_only=True
    )

    class Meta:
        model = CustomerAccount
        fields = [
            "id", "customer", "customer_name",
            "account_type", "account_number", "account_name",
            "bank_or_network", "is_primary", "is_verified",
            "created_at",
        ]
        read_only_fields = ["id", "is_verified", "created_at"]


class CustomerKYCSerializer(serializers.Serializer):
    kyc_status = serializers.ChoiceField(choices=Customer.KYCStatus.choices)
