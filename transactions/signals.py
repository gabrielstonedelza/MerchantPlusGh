from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AgentRequest, ProviderBalance


@receiver(post_save, sender=AgentRequest)
def agent_request_post_save(sender, instance, created, **kwargs):
    """Create notifications and broadcast real-time events for agent requests."""
    from notifications.models import Notification

    if created:
        company = instance.company
        settings = getattr(company, "settings", None)

        # Notify admins about large requests
        if settings and settings.notify_on_large_transaction:
            if instance.amount >= settings.large_transaction_threshold:
                from accounts.models import Membership
                admin_memberships = Membership.objects.filter(
                    company=company, role="owner", is_active=True,
                )
                for m in admin_memberships:
                    Notification.objects.create(
                        company=company, user=m.user,
                        category=Notification.Category.TRANSACTION,
                        title="Large Request Alert",
                        message=(
                            f"A {instance.transaction_type} request of {instance.amount} GHS "
                            f"({instance.reference}) was submitted and is awaiting your approval."
                        ),
                        related_object_id=str(instance.id),
                    )

        # Notify approvers — all new requests require approval
        if instance.status == "pending":
            from accounts.models import Membership
            approver_memberships = Membership.objects.filter(
                company=company, role="owner", is_active=True,
            )
            for m in approver_memberships:
                Notification.objects.create(
                    company=company, user=m.user,
                    category=Notification.Category.APPROVAL,
                    title="Approval Required",
                    message=(
                        f"A {instance.transaction_type} of {instance.amount} GHS "
                        f"({instance.reference}) requires your approval."
                    ),
                    related_object_id=str(instance.id),
                )

    # Broadcast agent request event to admin dashboard via WebSocket
    try:
        from .broadcast import broadcast_to_company
        broadcast_to_company(
            company_id=str(instance.company_id),
            event_type="transaction_event",
            data={
                "type": "transaction_update",
                "transaction": {
                    "id": str(instance.id),
                    "reference": instance.reference,
                    "requested_by": str(instance.requested_by_id) if instance.requested_by_id else None,
                    "requested_by_name": instance.requested_by.full_name if instance.requested_by else None,
                    "transaction_type": instance.transaction_type,
                    "channel": instance.channel,
                    "status": instance.status,
                    "amount": str(instance.amount),
                    "fee": str(instance.fee),
                    "customer": str(instance.customer_id) if instance.customer_id else None,
                    "customer_name": instance.customer.full_name if instance.customer else None,
                    "requested_at": instance.requested_at.isoformat() if instance.requested_at else None,
                    "is_new": created,
                },
            },
        )
    except Exception:
        pass  # Don't break requests if WebSocket layer is unavailable


@receiver(post_save, sender=ProviderBalance)
def provider_balance_post_save(sender, instance, **kwargs):
    """Broadcast balance changes to admin dashboard."""
    try:
        from .broadcast import broadcast_to_company
        broadcast_to_company(
            company_id=str(instance.company_id),
            event_type="balance_event",
            data={
                "type": "balance_change",
                "balance": {
                    "user_id": str(instance.user_id),
                    "user_name": instance.user.full_name,
                    "provider": instance.provider,
                    "balance": str(instance.balance),
                    "starting_balance": str(instance.starting_balance),
                },
            },
        )
    except Exception:
        pass
