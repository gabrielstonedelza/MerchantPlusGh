from django.contrib import admin
from .models import Customer, CustomerAccount


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        "full_name", "phone", "email", "registered_by",
        "status", "kyc_status", "loyalty_points", "created_at",
    ]
    list_filter = ["status", "kyc_status"]
    search_fields = ["full_name", "phone", "email"]
    autocomplete_fields = ["registered_by"]
    raw_id_fields = ["referred_by"]
    readonly_fields = ["id", "created_at", "updated_at"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter registered_by to only show users with active memberships (agents/owners)."""
        if db_field.name == "registered_by":
            from accounts.models import Membership
            active_user_ids = (
                Membership.objects.filter(is_active=True)
                .values_list("user_id", flat=True)
                .distinct()
            )
            kwargs["queryset"] = db_field.related_model.objects.filter(
                id__in=active_user_ids
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(CustomerAccount)
class CustomerAccountAdmin(admin.ModelAdmin):
    list_display = [
        "account_name", "account_number", "bank_or_network",
        "account_type", "customer", "is_primary",
    ]
    list_filter = ["account_type", "is_verified"]
    search_fields = ["account_name", "account_number", "customer__full_name"]
