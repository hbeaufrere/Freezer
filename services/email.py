"""Transactional email via Resend.

Used to send temporary passwords to admin-created users. Falls back to
printing the email body to stdout if RESEND_API_KEY is not configured,
which is useful for local development.
"""

import resend

import config


def _client_configured() -> bool:
    return bool(config.RESEND_API_KEY)


def _send(to: str, subject: str, html: str, text: str) -> None:
    if not _client_configured():
        # Dev fallback: log so the admin can grab the temp password locally
        print(f"\n[email:dev] To: {to}\n[email:dev] Subject: {subject}\n{text}\n")
        return
    resend.api_key = config.RESEND_API_KEY
    resend.Emails.send({
        'from': config.EMAIL_FROM,
        'to': [to],
        'subject': subject,
        'html': html,
        'text': text,
    })


def send_temp_password(to: str, full_name: str, temp_password: str, role_label: str) -> None:
    """Email a newly-created user their temporary password."""
    login_url = config.APP_BASE_URL.rstrip('/') + '/login'
    greeting = f"Hello {full_name}," if full_name else "Hello,"

    text = (
        f"{greeting}\n\n"
        f"An account has been created for you on the CLIPR Repository / Raptor Biobank.\n\n"
        f"Role: {role_label}\n"
        f"Email: {to}\n"
        f"Temporary password: {temp_password}\n\n"
        f"Please log in at {login_url} and set a new password on your first sign-in.\n\n"
        f"This temporary password should be changed immediately. If you did not expect\n"
        f"this email, please ignore it.\n"
    )

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; color: #1e293b;">
        <h2 style="color: #0f172a; margin-bottom: 8px;">Welcome to the CLIPR Repository</h2>
        <p style="color: #475569;">{greeting}</p>
        <p>An account has been created for you on the <strong>CLIPR Repository / Raptor Biobank</strong>.</p>
        <table style="background: #f1f5f9; border-radius: 8px; padding: 16px; width: 100%; margin: 16px 0; border-collapse: separate;">
            <tr><td style="padding: 4px 8px; color: #64748b;">Role</td><td style="padding: 4px 8px;"><strong>{role_label}</strong></td></tr>
            <tr><td style="padding: 4px 8px; color: #64748b;">Email</td><td style="padding: 4px 8px;"><strong>{to}</strong></td></tr>
            <tr><td style="padding: 4px 8px; color: #64748b;">Temporary password</td><td style="padding: 4px 8px; font-family: monospace; font-size: 1.05rem;"><strong>{temp_password}</strong></td></tr>
        </table>
        <p>
            <a href="{login_url}" style="display: inline-block; background: #2563eb; color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: 600;">Log in and set your password</a>
        </p>
        <p style="color: #64748b; font-size: 0.9rem; margin-top: 24px;">
            You will be prompted to choose a new password on your first sign-in.
            If you did not expect this email, please ignore it.
        </p>
    </div>
    """

    _send(to, "Your CLIPR Biobank account", html, text)
