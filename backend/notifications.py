"""Email notification utility for partner-application lifecycle events.

Sprint 6 / FPRM-93. Wraps ``smtplib`` with a dev-mode stdout fallback: if
``SMTP_HOST``/``SMTP_USER`` env vars are missing, ``send_email`` logs the email
content to stdout instead of attempting an SMTP connection. ``send_email``
never raises — callers wrap their use site in ``try/except`` as defence in depth,
but the function itself swallows SMTP errors so email failures cannot break an
API endpoint.

Notification templates are plain HTML strings; no Jinja or other template engine
to keep the dependency footprint minimal.
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body_html: str) -> None:
    """Send a single HTML email. Logs to stdout in dev mode. Never raises."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    email_from = os.getenv("EMAIL_FROM", "noreply@fracttal.com")

    if not smtp_host or not smtp_user:
        logger.info("[DEV MODE EMAIL] to=%s subject=%s", to, subject)
        logger.info("[DEV MODE EMAIL BODY]\n%s", body_html)
        print(f"[DEV MODE EMAIL] to={to} subject={subject}")
        print(body_html)
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = email_from
        msg["To"] = to
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(email_from, [to], msg.as_string())
    except Exception as exc:  # pragma: no cover  — never let email errors crash an endpoint
        logger.error("Email send failed to=%s subject=%s: %s", to, subject, exc)


# ----- runtime config exposed to templates -----


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "https://fracttal-prm-frontend-production.up.railway.app").rstrip("/")


def _channel_ops_email() -> str:
    return os.getenv("CHANNEL_OPS_EMAIL", "")


def _ref(application) -> str:
    return str(application.id)[:8].upper()


# ----- lifecycle templates -----


def notify_application_submitted(application) -> None:
    send_email(
        to=application.applicant_email,
        subject=f"Fracttal Partner Application Received — Reference #{_ref(application)}",
        body_html=(
            f"<p>Dear {application.applicant_name or 'Applicant'},</p>"
            f"<p>Thank you for applying to become a Fracttal Distribution Partner. "
            f"We have received your application and will review it within 5 business days.</p>"
            f"<p>Your application reference: <strong>{_ref(application)}</strong></p>"
            f"<p>The Fracttal Partner Team</p>"
        ),
    )
    ops_email = _channel_ops_email()
    if ops_email:
        send_email(
            to=ops_email,
            subject=(
                f"New partner application: "
                f"{application.legal_name or application.applicant_name or _ref(application)}"
            ),
            body_html=(
                f"<p>A new partner application has been submitted.</p>"
                f"<ul>"
                f"<li>Applicant: {application.applicant_name or '—'}</li>"
                f"<li>Company: {application.legal_name or '—'}</li>"
                f"<li>Email: {application.applicant_email}</li>"
                f"<li>Reference: {_ref(application)}</li>"
                f"</ul>"
                f"<p>Review at: {_frontend_url()}/internal/applications/{application.id}</p>"
            ),
        )


def notify_info_required(application, message: str) -> None:
    resume_url = (
        f"{_frontend_url()}/resume-application?id={application.id}"
        f"&draft_token={application.draft_token or ''}"
    )
    send_email(
        to=application.applicant_email,
        subject="Fracttal Partner Application — Additional Information Required",
        body_html=(
            f"<p>Dear {application.applicant_name or 'Applicant'},</p>"
            f"<p>Our team has reviewed your application and requires additional information "
            f"before we can proceed.</p>"
            f"<p><strong>Reviewer message:</strong></p>"
            f"<blockquote>{message}</blockquote>"
            f"<p>Please <a href=\"{resume_url}\">click here to update your application</a>.</p>"
            f"<p>The Fracttal Partner Team</p>"
        ),
    )


def notify_application_approved(application, invite_token: str = "") -> None:
    invite_url = f"{_frontend_url()}/accept-invite?token={invite_token}" if invite_token else ""
    invite_link = (
        f'<p>Please accept your portal invitation: <a href="{invite_url}">Accept Invitation</a></p>'
        f'<p>This invitation expires in 7 days.</p>'
    ) if invite_url else ""
    send_email(
        to=application.applicant_email,
        subject="Congratulations — Your Fracttal Partner Application Has Been Approved",
        body_html=(
            f"<p>Dear {application.applicant_name or 'Applicant'},</p>"
            f"<p>We are delighted to inform you that your application to become a Fracttal "
            f"Distribution Partner has been approved.</p>"
            f"{invite_link}"
            f"<p>Welcome to the Fracttal Partner Network.</p>"
            f"<p>The Fracttal Partner Team</p>"
        ),
    )


def notify_application_rejected(application, rejection_reason: str) -> None:
    send_email(
        to=application.applicant_email,
        subject="Fracttal Partner Application — Update on Your Application",
        body_html=(
            f"<p>Dear {application.applicant_name or 'Applicant'},</p>"
            f"<p>Thank you for your interest in becoming a Fracttal Distribution Partner. "
            f"After careful review we are unable to approve your application at this time.</p>"
            f"<p><strong>Reason:</strong> {rejection_reason}</p>"
            f"<p>If you believe this decision was made in error or your circumstances change, "
            f"you are welcome to reapply in the future.</p>"
            f"<p>The Fracttal Partner Team</p>"
        ),
    )
