import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

def send_assignment_email(
    to_email: str,
    assignment_title: str,
    deadline: str,
    access_url: str
):
    # DEV MODE — just print if SMTP not configured
    if settings.ENV == "development":
        print(f"[DEV EMAIL] To: {to_email}")
        print(f"[DEV EMAIL] Assignment: {assignment_title}")
        print(f"[DEV EMAIL] Deadline: {deadline}")
        print(f"[DEV EMAIL] Link: {access_url}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"You have been assigned: {assignment_title}"
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to_email

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #01696f;">Assignment: {assignment_title}</h2>
        <p>You have been invited to complete an assignment.</p>
        <p><strong>Deadline:</strong> {deadline}</p>
        <br>
        <a href="{access_url}"
           style="padding:12px 24px; background:#01696f; color:white;
                  border-radius:6px; text-decoration:none; font-weight:bold;">
            Start Assignment
        </a>
        <br><br>
        <p style="color:#999; font-size:12px;">
            If the button doesn't work, copy this link: {access_url}
        </p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())


def send_password_reset_email(to_email: str, reset_link: str):
    """Send a password reset email to the admin."""
    # DEV MODE — just print
    if settings.ENV == "development":
        print(f"[DEV EMAIL] Password reset for: {to_email}")
        print(f"[DEV EMAIL] Reset link: {reset_link}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "PulseLMS — Reset Your Admin Password"
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to_email

    html = f"""
    <html>
    <body style="margin:0; padding:0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f6f9;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px; margin:40px auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">
            <!-- Header -->
            <tr>
                <td style="background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); padding: 32px 40px; text-align:center;">
                    <h1 style="color:#fff; margin:0; font-size:22px; font-weight:700; letter-spacing:-0.5px;">PulseLMS</h1>
                    <p style="color:rgba(255,255,255,0.8); margin:8px 0 0; font-size:13px;">Admin Password Reset</p>
                </td>
            </tr>
            <!-- Body -->
            <tr>
                <td style="padding: 36px 40px 20px;">
                    <h2 style="color:#111827; font-size:20px; font-weight:700; margin:0 0 12px;">Reset your password</h2>
                    <p style="color:#6b7280; font-size:14px; line-height:1.6; margin:0 0 24px;">
                        We received a request to reset your admin password. Click the button below to set a new password. This link will expire in <strong>30 minutes</strong>.
                    </p>
                    <table cellpadding="0" cellspacing="0" style="margin: 0 auto 24px;">
                        <tr>
                            <td style="background: linear-gradient(135deg, #2563eb, #3b82f6); border-radius:8px;">
                                <a href="{reset_link}"
                                   style="display:inline-block; padding:14px 36px; color:#fff; font-size:15px; font-weight:600; text-decoration:none; letter-spacing:0.3px;">
                                    Reset Password
                                </a>
                            </td>
                        </tr>
                    </table>
                    <p style="color:#9ca3af; font-size:12px; line-height:1.5; margin:0;">
                        If you didn't request this, you can safely ignore this email. Your password will not change.
                    </p>
                </td>
            </tr>
            <!-- Footer -->
            <tr>
                <td style="padding: 20px 40px 28px; border-top: 1px solid #f3f4f6;">
                    <p style="color:#d1d5db; font-size:11px; text-align:center; margin:0;">
                        If the button doesn't work, copy and paste this link:<br>
                        <a href="{reset_link}" style="color:#3b82f6; word-break:break-all;">{reset_link}</a>
                    </p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())