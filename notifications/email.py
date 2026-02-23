"""
Email notification utilities for Merchant+.

Sends transactional emails for:
  - Transaction alerts (large transactions, approvals, rejections)
  - Team invitations
  - Daily summary reports
  - Security alerts (password change, new login)
"""

import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_notification_email(
    to_email: str,
    subject: str,
    message: str,
    html_message: str | None = None,
):
    """
    Send a single notification email.
    Fails silently in development (console backend), logs errors in production.
    """
    try:
        send_mail(
            subject=f"[Merchant+] {subject}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)


def send_transaction_alert(user_email: str, user_name: str, tx_data: dict):
    """Notify a manager about a large or pending-approval transaction."""
    subject = f"Transaction Alert: {tx_data['reference']}"
    message = (
        f"Hi {user_name},\n\n"
        f"A transaction requires your attention:\n\n"
        f"  Reference: {tx_data['reference']}\n"
        f"  Type:      {tx_data['type']}\n"
        f"  Amount:    {tx_data['currency']} {tx_data['amount']}\n"
        f"  Status:    {tx_data['status']}\n"
        f"  Initiated: {tx_data['initiated_by']}\n\n"
        f"Please log in to your Merchant+ dashboard to review.\n\n"
        f"— Merchant+ Team"
    )
    send_notification_email(user_email, subject, message)


def send_invitation_email(
    to_email: str,
    company_name: str,
    role: str,
    token: str,
    invited_by: str = "",
):
    """Send a team invitation email with an accept link."""
    accept_url = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
    subject = f"You're invited to join {company_name}"
    message = (
        f"Hello,\n\n"
        f"{'You have been invited by ' + invited_by + ' to' if invited_by else 'You have been invited to'}"
        f" join {company_name} on Merchant+ as an {role}.\n\n"
        f"Click the link below to accept your invitation and create your account:\n\n"
        f"  {accept_url}\n\n"
        f"This invitation expires in 7 days.\n\n"
        f"If you did not expect this invitation, you can safely ignore this email.\n\n"
        f"— The Merchant+ Team"
    )
    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #D4A843;">
            <h1 style="color: #D4A843; margin: 0;">Merchant+</h1>
        </div>
        <div style="padding: 30px 0;">
            <p style="color: #333; font-size: 16px;">Hello,</p>
            <p style="color: #333; font-size: 16px;">
                {'<strong>' + invited_by + '</strong> has invited you to' if invited_by else 'You have been invited to'}
                join <strong>{company_name}</strong> on Merchant+ as an <strong>{role}</strong>.
            </p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{accept_url}"
                   style="background-color: #D4A843; color: #000; padding: 14px 32px;
                          text-decoration: none; border-radius: 8px; font-weight: bold;
                          font-size: 16px; display: inline-block;">
                    Accept Invitation
                </a>
            </div>
            <p style="color: #666; font-size: 14px;">
                Or copy and paste this link in your browser:<br>
                <a href="{accept_url}" style="color: #D4A843;">{accept_url}</a>
            </p>
            <p style="color: #666; font-size: 14px;">This invitation expires in 7 days.</p>
            <p style="color: #999; font-size: 12px;">
                If you did not expect this invitation, you can safely ignore this email.
            </p>
        </div>
        <div style="border-top: 1px solid #eee; padding-top: 15px; text-align: center;">
            <p style="color: #999; font-size: 12px;">&copy; Merchant+ — Powering Payments in Ghana</p>
        </div>
    </div>
    """
    send_notification_email(to_email, subject, message, html_message=html_message)


def send_daily_summary(
    to_email: str,
    user_name: str,
    company_name: str,
    summary: dict,
):
    """Send end-of-day summary to company admins."""
    subject = f"Daily Summary — {company_name}"
    message = (
        f"Hi {user_name},\n\n"
        f"Here's your daily summary for {company_name}:\n\n"
        f"  Transactions Today:  {summary['total_transactions']}\n"
        f"  Total Deposits:      GHS {summary['total_deposits']}\n"
        f"  Total Withdrawals:   GHS {summary['total_withdrawals']}\n"
        f"  Fees Collected:      GHS {summary['total_fees']}\n"
        f"  Pending Approvals:   {summary['pending_approvals']}\n\n"
        f"Log in for full details: {summary.get('dashboard_url', 'your Merchant+ dashboard')}\n\n"
        f"— Merchant+ Team"
    )
    send_notification_email(to_email, subject, message)


def send_security_alert(to_email: str, user_name: str, event: str, details: str):
    """Send security event notification (password change, suspicious login, etc)."""
    subject = f"Security Alert: {event}"
    message = (
        f"Hi {user_name},\n\n"
        f"We detected a security-related event on your Merchant+ account:\n\n"
        f"  Event:   {event}\n"
        f"  Details: {details}\n\n"
        f"If this wasn't you, please change your password immediately.\n\n"
        f"— Merchant+ Security Team"
    )
    send_notification_email(to_email, subject, message)
