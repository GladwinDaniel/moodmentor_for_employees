import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def get_env_or_secret(key: str, default=""):
    val = os.getenv(key)
    if val:
        return val.strip()
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return default

def get_smtp_config():
    email = get_env_or_secret("SMTP_EMAIL", "").strip()
    # Google App Passwords often contain 4-character spaces (e.g. "abcd efgh ijkl mnop")
    pw = get_env_or_secret("SMTP_APP_PASSWORD", "").strip().replace(" ", "").replace('"', '').replace("'", "")
    host = get_env_or_secret("SMTP_HOST", "smtp.gmail.com").strip()
    port_str = get_env_or_secret("SMTP_PORT", "587").strip()
    try:
        port = int(port_str)
    except ValueError:
        port = 587
    return email, pw, host, port

def send_otp(to_email: str, code: str, purpose: str = "signup"):
    email, pw, host, port = get_smtp_config()
    to_email = (to_email or "").strip().lower()

    if not email or not pw:
        return False, "SMTP configuration missing: 'SMTP_EMAIL' or 'SMTP_APP_PASSWORD' is not configured in Streamlit Secrets or .env file."

    purpose_titles = {
        "signup": "Account Verification",
        "password_reset": "Password Reset",
        "email_change": "Email Change Verification",
    }
    action_text = {
        "signup": "verifying your MoodMentor account",
        "password_reset": "resetting your MoodMentor password",
        "email_change": "changing your MoodMentor account email",
    }.get(purpose, "verification")

    title = purpose_titles.get(purpose, "Verification Code")
    subject = f"MoodMentor - {title} Code: {code}"

    text_body = f"""Hello,

Your 6-digit MoodMentor verification code for {action_text} is:

{code}

This code is valid for 10 minutes. If you did not request this, please ignore this email.

Best regards,
MoodMentor Wellness Team
"""

    html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px;">
  <div style="max-width: 520px; margin: 0 auto; background: #ffffff; padding: 32px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
    <div style="display: flex; align-items: center; margin-bottom: 20px;">
      <h2 style="color: #4338ca; margin: 0; font-size: 22px;">🧘 MoodMentor</h2>
    </div>
    <p style="color: #334155; font-size: 15px; line-height: 1.5;">
      Use the one-time verification code below for <strong>{action_text}</strong>:
    </p>
    <div style="background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%); border: 1px dashed #6366f1; border-radius: 10px; padding: 20px; text-align: center; margin: 24px 0;">
      <span style="font-size: 34px; font-weight: 700; letter-spacing: 8px; color: #4338ca; font-family: 'Courier New', monospace; display: inline-block; margin-left: 8px;">{code}</span>
    </div>
    <p style="color: #64748b; font-size: 13px; margin: 0 0 16px 0;">
      ⏰ This code expires in <strong>10 minutes</strong>.
    </p>
    <div style="border-top: 1px solid #e2e8f0; padding-top: 16px; margin-top: 24px;">
      <p style="color: #94a3b8; font-size: 12px; margin: 0; line-height: 1.4;">
        If you did not request this verification code, please ignore this email or reach out to support.
      </p>
    </div>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["From"] = f"MoodMentor <{email}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    errors = []

    # Strategy 1: Try Gmail SMTPS (Port 465, SSL) - usually most reliable on cloud platforms
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12) as s:
            s.login(email, pw)
            s.sendmail(email, to_email, msg.as_string())
        return True, "sent"
    except smtplib.SMTPAuthenticationError as e:
        return False, "Gmail Authentication Error (535): Invalid email or App Password. Make sure 2-Step Verification is ON in your Google Account and you generated a 16-character Google App Password."
    except Exception as e:
        errors.append(f"SSL/465 failed ({type(e).__name__}: {e})")

    # Strategy 2: Fallback to STARTTLS (Port 587)
    try:
        target_host = host if host != "smtp.gmail.com" else "smtp.gmail.com"
        target_port = port if host != "smtp.gmail.com" else 587
        with smtplib.SMTP(target_host, target_port, timeout=12) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(email, pw)
            s.sendmail(email, to_email, msg.as_string())
        return True, "sent"
    except smtplib.SMTPAuthenticationError as e:
        return False, "Gmail Authentication Error (535): Invalid email or App Password. Make sure 2-Step Verification is ON in your Google Account and you generated a 16-character Google App Password."
    except Exception as e:
        errors.append(f"TLS/587 failed ({type(e).__name__}: {e})")

    return False, f"SMTP Connection Failed: {' | '.join(errors)}"
