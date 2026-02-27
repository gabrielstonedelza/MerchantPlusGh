from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Customer


@receiver(post_save, sender=Customer)
def customer_post_save(sender, instance, created, **kwargs):
    """Broadcast customer registration/update events to all admin dashboards."""
    try:
        from transactions.broadcast import broadcast_to_company
        from accounts.models import Membership

        # Since customers are shared across companies, broadcast to all
        # companies that have active memberships
        company_ids = (
            Membership.objects.filter(is_active=True)
            .values_list("company_id", flat=True)
            .distinct()
        )

        event_data = {
            "type": "customer_update",
            "customer": {
                "id": str(instance.id),
                "full_name": instance.full_name,
                "phone": instance.phone,
                "status": instance.status,
                "kyc_status": instance.kyc_status,
                "registered_by": (
                    instance.registered_by.full_name
                    if instance.registered_by
                    else None
                ),
                "created_at": (
                    instance.created_at.isoformat() if instance.created_at else None
                ),
                "is_new": created,
                "action": "created" if created else "updated",
            },
        }

        for company_id in company_ids:
            broadcast_to_company(
                company_id=str(company_id),
                event_type="customer_event",
                data=event_data,
            )
    except Exception:
        pass


@receiver(post_delete, sender=Customer)
def customer_post_delete(sender, instance, **kwargs):
    """Broadcast customer deletion events to all admin dashboards."""
    try:
        from transactions.broadcast import broadcast_to_company
        from accounts.models import Membership

        company_ids = (
            Membership.objects.filter(is_active=True)
            .values_list("company_id", flat=True)
            .distinct()
        )

        event_data = {
            "type": "customer_update",
            "customer": {
                "id": str(instance.id),
                "full_name": instance.full_name,
                "phone": instance.phone,
                "action": "deleted",
            },
        }

        for company_id in company_ids:
            broadcast_to_company(
                company_id=str(company_id),
                event_type="customer_event",
                data=event_data,
            )
    except Exception:
        pass
