"""Email notifications.

One message goes out when somebody leaves samples at a satellite freezer, so
the lab learns about a drop without having to open the app. Everything is
configured by environment variables and the whole thing is optional: with no
SMTP settings the app behaves exactly as it did before.

Sending is deliberately best-effort. A drop-off that is safely recorded must
never fail because a mail server was slow, so every error here is logged and
swallowed — the counter in the database is the record, the email is a courtesy.

The send is synchronous rather than backgrounded. On a serverless platform the
function instance is frozen the moment the response goes out, so a worker
thread would be killed mid-handshake often enough to lose messages silently.
"""

import html
import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)

# Long enough for a TLS handshake to a busy mail server, short enough that the
# person standing at the freezer is not left staring at a spinner.
SMTP_TIMEOUT = 10


def settings():
    """Mail configuration from the environment, or None if it isn't set up.

    Read on each call rather than at import, so changing the environment takes
    effect on the next request instead of the next deploy.
    """
    user = os.environ.get('SMTP_USER', '').strip()
    password = os.environ.get('SMTP_PASSWORD', '').strip()
    recipient = os.environ.get('NOTIFY_EMAIL', '').strip() or user

    if not (user and password and recipient):
        return None

    return {
        'host': os.environ.get('SMTP_HOST', 'smtp.gmail.com').strip(),
        'port': int(os.environ.get('SMTP_PORT', '587')),
        'user': user,
        'password': password,
        'sender': os.environ.get('SMTP_FROM', '').strip() or user,
        'recipient': recipient,
    }


def configured():
    return settings() is not None


# ------------------------------------------------------------
# Message building
# ------------------------------------------------------------

def _plural(n, word):
    return f'{n} {word}' if n == 1 else f'{n} {word}s'


def _age(days):
    if days is None:
        return ''
    if days == 0:
        return 'today'
    return f'oldest {_plural(days, "day")}'


def dropoff_subject(site_code, added, waiting_here):
    return (f'{_plural(added, "sample")} dropped at {site_code}'
            f' — {waiting_here} now waiting')


def build_dropoff_message(site, added, sites, dropped_by=None, note=None, app_url=None):
    """Compose the drop-off email.

    ``sites`` is the summary of every satellite site, so the message answers
    "and what about the other freezer?" without a second trip to the app.
    """
    here = next((s for s in sites if s['id'] == site['id']), None)
    waiting_here = here['pending_samples'] if here else added
    total = sum(s['pending_samples'] for s in sites)

    msg = EmailMessage()
    msg['Subject'] = dropoff_subject(site['code'], added, waiting_here)

    lines = [
        f'Someone added {_plural(added, "sample")} to the {site["code"]} freezer'
        f' ({site["name"]}).',
        '',
    ]
    if dropped_by:
        lines.append(f'Left by: {dropped_by}')
    if note:
        lines.append(f'Note: {note}')
    if dropped_by or note:
        lines.append('')

    lines.append('Waiting for collection:')
    for s in sites:
        age = _age(s['oldest_age_days']) if s['pending_samples'] else ''
        suffix = f'  ({age})' if age else ''
        lines.append(f'  {s["code"]:<6} {s["pending_samples"]:>4}{suffix}')
    lines.append('')
    lines.append(f'Total waiting across all sites: {total}')

    if app_url:
        lines += ['', f'Open the freezer: {app_url}']

    lines += ['', '-- ', 'CLIPR Sample Repository and Raptor Biobank']
    msg.set_content('\n'.join(lines))

    rows = ''.join(
        f'<tr><td style="padding:6px 18px 6px 0;font-weight:600">{html.escape(s["code"])}</td>'
        f'<td style="padding:6px 18px 6px 0;text-align:right">{s["pending_samples"]}</td>'
        f'<td style="padding:6px 0;color:#5c7189">'
        f'{html.escape(_age(s["oldest_age_days"]) if s["pending_samples"] else "")}</td></tr>'
        for s in sites
    )
    detail = ''
    if dropped_by:
        detail += f'<p style="margin:0 0 4px">Left by <strong>{html.escape(dropped_by)}</strong></p>'
    if note:
        detail += f'<p style="margin:0 0 4px">Note: {html.escape(note)}</p>'

    link = (f'<p style="margin:22px 0 0"><a href="{html.escape(app_url)}"'
            f' style="color:#022851">Open the freezer</a></p>') if app_url else ''

    msg.add_alternative(f"""\
<html><body style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
     color:#0a1c30;line-height:1.5">
  <div style="height:5px;background:#ffbf00;border-radius:3px;max-width:460px"></div>
  <h2 style="margin:18px 0 6px;font-size:19px">
    {html.escape(_plural(added, 'sample'))} added at {html.escape(site['code'])}
  </h2>
  <p style="margin:0 0 14px;color:#5c7189">{html.escape(site['name'])}</p>
  {detail}
  <table style="border-collapse:collapse;margin:14px 0 0;font-size:15px">
    <tr><th colspan="3" style="text-align:left;padding:0 0 4px;font-size:13px;
        text-transform:uppercase;letter-spacing:.06em;color:#5c7189">
        Waiting for collection</th></tr>
    {rows}
    <tr><td style="padding:8px 18px 0 0;border-top:1px solid #c2cedd;font-weight:600">Total</td>
        <td style="padding:8px 18px 0 0;border-top:1px solid #c2cedd;text-align:right;
            font-weight:600">{total}</td>
        <td style="border-top:1px solid #c2cedd"></td></tr>
  </table>
  {link}
  <p style="margin:26px 0 0;font-size:12px;color:#5c7189;border-top:1px solid #c2cedd;
     padding-top:12px">CLIPR Sample Repository and Raptor Biobank</p>
</body></html>""", subtype='html')

    return msg


# ------------------------------------------------------------
# Sending
# ------------------------------------------------------------

def deliver(msg):
    """Send a prepared message. Returns True if it went out.

    Never raises: callers are in the middle of a request that has already done
    the thing that mattered.
    """
    config = settings()
    if config is None:
        log.info('Email not configured; skipping "%s"', msg['Subject'])
        return False

    msg['From'] = config['sender']
    msg['To'] = config['recipient']

    try:
        if config['port'] == 465:
            with smtplib.SMTP_SSL(config['host'], config['port'],
                                  timeout=SMTP_TIMEOUT) as smtp:
                smtp.login(config['user'], config['password'])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(config['host'], config['port'],
                              timeout=SMTP_TIMEOUT) as smtp:
                smtp.starttls()
                smtp.login(config['user'], config['password'])
                smtp.send_message(msg)
    except Exception:
        # Including the recipient, because a typo there is the likeliest cause.
        log.exception('Could not send "%s" to %s', msg['Subject'], config['recipient'])
        return False

    log.info('Sent "%s" to %s', msg['Subject'], config['recipient'])
    return True


def notify_dropoff(site, added, sites, dropped_by=None, note=None, app_url=None):
    if not configured():
        return False
    return deliver(build_dropoff_message(site, added, sites, dropped_by, note, app_url))


def send_test_email(app_url=None):
    """Prove the settings work, without waiting for someone to visit a freezer."""
    msg = EmailMessage()
    msg['Subject'] = 'Freezer notifications are working'
    msg.set_content(
        'This is a test from the CLIPR Sample Repository and Raptor Biobank.\n\n'
        'Notifications are set up correctly. From now on you will get an email '
        'whenever somebody leaves samples at CRC or VMTH.\n'
        + (f'\nOpen the freezer: {app_url}\n' if app_url else '')
    )
    return deliver(msg)
