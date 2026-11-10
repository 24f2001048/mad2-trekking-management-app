import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")


def send_email(to, subject, html):
    user = os.environ.get("MAIL_USER")
    password = os.environ.get("MAIL_PASSWORD")

    if not user or not password:
        # No mail account configured: save the email as a file so it can still be shown
        os.makedirs(OUT_DIR, exist_ok=True)
        safe_to = re.sub(r"[^a-zA-Z0-9]", "_", to)
        path = os.path.join(OUT_DIR, f"email_{datetime.now().strftime('%H%M%S%f')}_{safe_to}.html")
        with open(path, "w") as f:
            f.write(f"<p><b>To:</b> {to}<br><b>Subject:</b> {subject}</p><hr>{html}")
        print("Email saved to file:", path)
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, password)
        server.sendmail(user, to, msg.as_string())