"""Email notification utility for partner-application lifecycle events.

Sprint 6 / FPRM-93; transport rewritten in Sprint 26 PR A / FPRM-462 (AD-47).
``send_email`` now delivers via the **Resend HTTPS API** (POST
https://api.resend.com/emails over port 443) — SMTP is permanently blocked on
Railway on every port (25/465/587/2525), so ``smtplib`` could never deliver in
production. When ``RESEND_API_KEY`` is absent/empty (local/dev/CI) it falls back
to logging the email to stdout so flows stay testable without credentials.
``send_email`` never raises — callers wrap their use site in ``try/except`` as
defence in depth (AD-13), and the function itself swallows transport errors so an
email failure can never surface as a 500 on a user-facing endpoint.

Email links are built from ``PUBLIC_APP_URL`` (see ``public_app_url``), never from
``FRONTEND_URL`` — the latter is the CORS allowlist and is ``*`` on Railway, which
cannot form a usable link.

Notification templates are plain HTML strings; no Jinja or other template engine
to keep the dependency footprint minimal.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
DEFAULT_EMAIL_FROM = "noreply@contact.synproconsulting.co"


def send_email(to: str, subject: str, body_html: str) -> None:
    """Send a single HTML email via Resend. Logs to stdout when no API key is
    configured (dev/CI). Never raises — a transient email error must not break
    the calling endpoint."""
    resend_api_key = os.getenv("RESEND_API_KEY")
    email_from = os.getenv("EMAIL_FROM", DEFAULT_EMAIL_FROM)

    if not resend_api_key:
        # Dev / CI fallback — no credentials, log to stdout so flows stay testable
        # and CI never makes a real network call to api.resend.com.
        logger.info("[DEV MODE EMAIL] to=%s subject=%s", to, subject)
        logger.info("[DEV MODE EMAIL BODY]\n%s", body_html)
        print(f"[DEV MODE EMAIL] to={to} subject={subject}")
        print(body_html)
        return

    try:
        resp = httpx.post(
            RESEND_ENDPOINT,
            headers={
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
            },
            json={"from": email_from, "to": [to], "subject": subject, "html": body_html},
            timeout=10.0,
        )
        if resp.status_code >= 400:
            # Warning, not exception — never propagate as a 500 to the API caller.
            logger.warning(
                "Resend email failed to=%s subject=%s status=%s body=%s",
                to, subject, resp.status_code, resp.text,
            )
    except Exception as exc:  # never let a transport error crash an endpoint
        logger.warning("Resend email error to=%s subject=%s: %s", to, subject, exc)


# ----- runtime config exposed to templates -----


def public_app_url() -> str:
    """Base URL for user-facing email links (password reset, invite accept,
    application resume).

    Uses ``PUBLIC_APP_URL`` — NOT ``FRONTEND_URL``. ``FRONTEND_URL`` is the CORS
    allowlist and is set to ``*`` on Railway, which cannot build a usable link.
    Production must set ``PUBLIC_APP_URL`` on the ``fracttal-prm-backend`` service;
    when it is absent we log a warning and fall back to the local dev origin so CI
    passes without the var rather than silently producing broken links.
    """
    url = os.getenv("PUBLIC_APP_URL")
    if not url:
        logger.warning(
            "PUBLIC_APP_URL not set — falling back to http://localhost:5173 for email links"
        )
        return "http://localhost:5173"
    return url.rstrip("/")


def _frontend_url() -> str:
    # Email links must use PUBLIC_APP_URL (AD-47). The lifecycle templates below
    # build links too, so this delegates rather than reading FRONTEND_URL (='*'
    # on Railway → broken links). Kept as a thin alias to avoid churning the
    # existing notify_* call sites.
    return public_app_url()


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
