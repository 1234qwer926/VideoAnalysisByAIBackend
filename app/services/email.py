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