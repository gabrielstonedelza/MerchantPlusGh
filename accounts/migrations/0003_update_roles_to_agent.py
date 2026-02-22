"""
Migration to consolidate roles from owner/admin/manager/teller to owner/agent.
Converts all non-owner roles (admin, manager, teller) to 'agent'.
"""
from django.db import migrations, models


def convert_roles_forward(apps, schema_editor):
    """Convert admin, manager, teller roles to agent."""
    Membership = apps.get_model("accounts", "Membership")
    Membership.objects.filter(role__in=["admin", "manager", "teller"]).update(role="agent")

    Invitation = apps.get_model("accounts", "Invitation")
    Invitation.objects.filter(role__in=["admin", "manager", "teller"]).update(role="agent")


def convert_roles_backward(apps, schema_editor):
    """Revert agent roles back to teller (best-effort reverse)."""
    Membership = apps.get_model("accounts", "Membership")
    Membership.objects.filter(role="agent").update(role="teller")

    Invitation = apps.get_model("accounts", "Invitation")
    Invitation.objects.filter(role="agent").update(role="teller")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        # First convert existing data
        migrations.RunPython(convert_roles_forward, convert_roles_backward),
        # Then update the field choices and default
        migrations.AlterField(
            model_name="membership",
            name="role",
            field=models.CharField(
                choices=[("owner", "Owner"), ("agent", "Agent")],
                default="agent",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="invitation",
            name="role",
            field=models.CharField(
                choices=[("owner", "Owner"), ("agent", "Agent")],
                default="agent",
                max_length=20,
            ),
        ),
    ]
