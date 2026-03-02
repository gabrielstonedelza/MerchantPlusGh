"""
Rename BankDeposit -> BankTransaction, simplify fields, and reduce MoMo ServiceType choices.

- Renames BankDeposit model to BankTransaction
- Renames depositor_name -> customer_name
- Removes slip_number and slip_image fields
- Updates related_name from bank_deposit_detail to bank_transaction_detail
- Removes send_money and receive_money from MobileMoneyTransaction.ServiceType
- Data migration: converts existing send_money -> cash_in, receive_money -> cash_out
"""

import django.db.models.deletion
from django.db import migrations, models


def migrate_service_types(apps, schema_editor):
    """Convert send_money -> cash_in and receive_money -> cash_out."""
    MobileMoneyTransaction = apps.get_model("transactions", "MobileMoneyTransaction")
    MobileMoneyTransaction.objects.filter(service_type="send_money").update(
        service_type="cash_in"
    )
    MobileMoneyTransaction.objects.filter(service_type="receive_money").update(
        service_type="cash_out"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0006_settlement_fields_and_provider_alignment"),
    ]

    operations = [
        # 1. Data migration: fix service_type values BEFORE constraining choices
        migrations.RunPython(migrate_service_types, migrations.RunPython.noop),

        # 2. Rename BankDeposit -> BankTransaction
        migrations.RenameModel(
            old_name="BankDeposit",
            new_name="BankTransaction",
        ),

        # 3. Rename depositor_name -> customer_name
        migrations.RenameField(
            model_name="banktransaction",
            old_name="depositor_name",
            new_name="customer_name",
        ),

        # 4. Remove slip_number
        migrations.RemoveField(
            model_name="banktransaction",
            name="slip_number",
        ),

        # 5. Remove slip_image
        migrations.RemoveField(
            model_name="banktransaction",
            name="slip_image",
        ),

        # 6. Update the OneToOneField related_name
        migrations.AlterField(
            model_name="banktransaction",
            name="transaction",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bank_transaction_detail",
                to="transactions.agentrequest",
            ),
        ),

        # 7. Update MobileMoneyTransaction service_type choices
        migrations.AlterField(
            model_name="mobilemoneytransaction",
            name="service_type",
            field=models.CharField(
                choices=[("cash_in", "Cash In"), ("cash_out", "Cash Out")],
                max_length=20,
            ),
        ),
    ]
