import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

log = logging.getLogger(__name__)

SUPPORT_EMAIL = "nlpnchu@gmail.com"

EMAIL_TEMPLATES = {
    "signup": {
        "subject": "【ChatNCHU】註冊驗證碼",
        "heading": "註冊驗證碼",
        "description": "您正在註冊 ChatNCHU 帳號，請使用以下驗證碼完成註冊：",
        "color": "#2E7D32",
        "bg_accent": "#E8F5E9",
    },
    "password_reset": {
        "subject": "【ChatNCHU】密碼重設驗證碼",
        "heading": "密碼重設驗證碼",
        "description": "您正在重設 ChatNCHU 帳號密碼，請使用以下驗證碼完成重設：",
        "color": "#E65100",
        "bg_accent": "#FFF3E0",
    },
}


def _build_email_html(code: str, purpose: str, to_email: str) -> str:
    t = EMAIL_TEMPLATES.get(purpose, EMAIL_TEMPLATES["signup"])
    return f"""\
<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI','Microsoft JhengHei',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:{t['color']};padding:24px 32px;text-align:center;">
            <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:1px;">ChatNCHU</h1>
            <p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:13px;">國立中興大學 AI 聊天平台</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px;">
            <h2 style="margin:0 0 12px;color:#333;font-size:18px;">{t['heading']}</h2>
            <p style="margin:0 0 24px;color:#555;font-size:14px;line-height:1.6;">{t['description']}</p>

            <!-- Code -->
            <div style="background:{t['bg_accent']};border-radius:8px;padding:20px;text-align:center;margin:0 0 24px;">
              <span style="font-size:36px;font-weight:700;letter-spacing:10px;color:{t['color']};">{code}</span>
            </div>

            <p style="margin:0 0 8px;color:#888;font-size:13px;">此驗證碼將於 <strong>15 分鐘</strong>後過期。</p>
            <p style="margin:0 0 0;color:#888;font-size:13px;">如果您未曾要求此驗證碼，請忽略此信件，您的帳號不會受到影響。</p>
          </td>
        </tr>

        <!-- Divider -->
        <tr><td style="padding:0 32px;"><hr style="border:none;border-top:1px solid #eee;margin:0;"></td></tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 32px;text-align:center;">
            <p style="margin:0 0 4px;color:#aaa;font-size:12px;">本信件由系統自動發送，請勿直接回覆。</p>
            <p style="margin:0;color:#aaa;font-size:12px;">如有任何問題，請聯繫
              <a href="mailto:{SUPPORT_EMAIL}" style="color:{t['color']};text-decoration:none;">{SUPPORT_EMAIL}</a>
            </p>
          </td>
        </tr>

      </table>

      <!-- Bottom note -->
      <p style="margin:16px 0 0;color:#ccc;font-size:11px;text-align:center;">&copy; NCHU NLP Lab</p>
    </td></tr>
  </table>
</body>
</html>"""


def send_verification_email(
    to_email: str,
    code: str,
    purpose: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_from: str,
    smtp_use_tls: bool = True,
) -> bool:
    try:
        t = EMAIL_TEMPLATES.get(purpose, EMAIL_TEMPLATES["signup"])

        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg["Subject"] = t["subject"]
        msg.attach(MIMEText(_build_email_html(code, purpose, to_email), "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        log.info(f"Verification email sent to {to_email}")
        return True
    except Exception as e:
        log.error(f"Failed to send email to {to_email}: {e}")
        return False
