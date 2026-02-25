"""
Migration: Rename Transaction → AgentRequest, remove deprecated fields,
rename created_at → requested_at, update Type/Status choices.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0002_add_cash_provider'),
    ]

    operations = [
        # 1. Rename the model (renames DB table and updates FK references in sub-models)
        migrations.RenameModel(
            old_name='Transaction',
            new_name='AgentRequest',
        ),

        # 2. Update Type choices — remove REVERSAL
        migrations.AlterField(
            model_name='agentrequest',
            name='transaction_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('deposit', 'Deposit'),
                    ('withdrawal', 'Withdrawal'),
                    ('transfer', 'Transfer'),
                    ('fee', 'Fee'),
                    ('commission', 'Commission'),
                ],
            ),
        ),

        # 3. Update Status choices — remove REVERSED
        migrations.AlterField(
            model_name='agentrequest',
            name='status',
            field=models.CharField(
                max_length=20,
                default='pending',
                choices=[
                    ('pending', 'Pending'),
                    ('approved', 'Approved'),
                    ('completed', 'Completed'),
                    ('rejected', 'Rejected'),
                    ('failed', 'Failed'),
                ],
            ),
        ),

        # 4. requires_approval now always True by default
        migrations.AlterField(
            model_name='agentrequest',
            name='requires_approval',
            field=models.BooleanField(default=True),
        ),

        # 5. Remove deprecated fields
        migrations.RemoveField(model_name='agentrequest', name='branch'),
        migrations.RemoveField(model_name='agentrequest', name='initiated_by'),
        migrations.RemoveField(model_name='agentrequest', name='net_amount'),
        migrations.RemoveField(model_name='agentrequest', name='description'),
        migrations.RemoveField(model_name='agentrequest', name='internal_notes'),
        migrations.RemoveField(model_name='agentrequest', name='reversed_transaction'),
        migrations.RemoveField(model_name='agentrequest', name='currency'),
        migrations.RemoveField(model_name='agentrequest', name='updated_at'),

        # 6. Rename created_at → requested_at
        migrations.RenameField(
            model_name='agentrequest',
            old_name='created_at',
            new_name='requested_at',
        ),

        # 7. Update model ordering to use new field name
        migrations.AlterModelOptions(
            name='agentrequest',
            options={'ordering': ['-requested_at']},
        ),

        # 8. Remove old indexes (reference the original index names from 0001_initial)
        migrations.RemoveIndex(
            model_name='agentrequest',
            name='transaction_company_471ff8_idx',  # company + created_at
        ),
        migrations.RemoveIndex(
            model_name='agentrequest',
            name='transaction_company_0ce1b6_idx',  # company + status
        ),
        migrations.RemoveIndex(
            model_name='agentrequest',
            name='transaction_company_d81ea8_idx',  # company + transaction_type
        ),
        migrations.RemoveIndex(
            model_name='agentrequest',
            name='transaction_referen_923a88_idx',  # reference
        ),

        # 9. Add new indexes with updated field names
        migrations.AddIndex(
            model_name='agentrequest',
            index=models.Index(fields=['company', 'requested_at'], name='agentreq_company_reqat_idx'),
        ),
        migrations.AddIndex(
            model_name='agentrequest',
            index=models.Index(fields=['company', 'status'], name='agentreq_company_status_idx'),
        ),
        migrations.AddIndex(
            model_name='agentrequest',
            index=models.Index(fields=['company', 'transaction_type'], name='agentreq_company_type_idx'),
        ),
        migrations.AddIndex(
            model_name='agentrequest',
            index=models.Index(fields=['reference'], name='agentreq_reference_idx'),
        ),

        # 10. Update sender_number to allow blank (needed for withdrawal flow)
        migrations.AlterField(
            model_name='mobilemoneytransaction',
            name='sender_number',
            field=models.CharField(max_length=20, blank=True),
        ),
    ]
