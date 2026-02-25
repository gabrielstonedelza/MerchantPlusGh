import logging

from django.contrib import admin
from .models import SubscriptionPlan, Company, Branch, APIKey, CompanySettings
from .webhooks import WebhookEndpoint, WebhookDelivery

logger = logging.getLogger(__name__)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "tier", "monthly_price", "max_users", "max_customers", "is_active"]
    list_filter = ["tier", "is_active"]
    search_fields = ["name"]


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        "name", "slug", "email", "subscription_plan", "subscription_status",
        "status", "is_verified", "created_at",
    ]
    list_filter = ["status", "subscription_status", "is_verified", "subscription_plan"]
    search_fields = ["name", "email", "slug"]
    readonly_fields = ["id", "created_at", "updated_at"]
    actions = ["approve_companies"]

    @admin.action(description="Approve selected companies (verify and activate)")
    def approve_companies(self, request, queryset):
        from notifications.email import send_company_approved_email

        updated = 0
        email_errors = 0
        for company in queryset.filter(status="pending_verification"):
            company.status = "active"
            company.is_verified = True
            company.save(update_fields=["status", "is_verified"])

            # Notify the owner
            if company.owner:
                try:
                    send_company_approved_email(
                        to_email=company.owner.email,
                        owner_name=company.owner.full_name,
                        company_name=company.name,
                    )
                except Exception as e:
                    logger.error("Failed to send approval email for %s: %s", company.name, e)
                    email_errors += 1
            updated += 1

        if email_errors:
            self.message_user(
                request,
                f"{updated} company(ies) approved, but {email_errors} email(s) failed to send. Check server logs.",
                level="warning",
            )
        else:
            self.message_user(request, f"{updated} company(ies) approved and owners notified.")

    def save_model(self, request, obj, form, change):
        """Send approval email when status is manually changed to active via the admin detail page."""
        if change and "status" in form.changed_data:
            old_status = form.initial.get("status")
            new_status = obj.status
            super().save_model(request, obj, form, change)

            if old_status == "pending_verification" and new_status == "active":
                # Also set is_verified = True automatically
                if not obj.is_verified:
                    obj.is_verified = True
                    obj.save(update_fields=["is_verified"])

                if obj.owner:
                    from notifications.email import send_company_approved_email
                    try:
                        send_company_approved_email(
                            to_email=obj.owner.email,
                            owner_name=obj.owner.full_name,
                            company_name=obj.name,
                        )
                        self.message_user(request, f"Approval email sent to {obj.owner.email}.")
                    except Exception as e:
                        logger.error("Failed to send approval email for %s: %s", obj.name, e)
                        self.message_user(
                            request,
                            f"Company approved but email to {obj.owner.email} failed: {e}",
                            level="warning",
                        )
        else:
            super().save_model(request, obj, form, change)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "city", "is_headquarters", "is_active"]
    list_filter = ["is_headquarters", "is_active"]
    search_fields = ["name", "company__name"]


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "key_prefix", "is_active", "last_used_at", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "company__name"]


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = ["company", "default_currency", "require_approval_above"]
    search_fields = ["company__name"]


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ["url", "company", "is_active", "failure_count", "last_triggered_at"]
    list_filter = ["is_active"]
    search_fields = ["url", "company__name"]
    readonly_fields = ["id", "secret", "created_at"]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ["event_type", "endpoint", "status", "response_status_code", "attempts", "created_at"]
    list_filter = ["status", "event_type"]
    readonly_fields = ["id", "payload", "response_body", "created_at"]
