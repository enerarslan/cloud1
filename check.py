import os, asyncio, sys, time, smtplib, ssl
from email.mime.text import MIMEText
from email.utils import formatdate
from playwright.async_api import async_playwright

FORM_URL = os.getenv("FORM_URL")

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO   = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM", EMAIL_USER or "")  # optional override
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() in {"1","true","yes"}

CLOSED_MARKERS = [
    "yanıt kabul edilmiyor", "yanıt kabul etmiyor",
    "form artık yanıt kabul etmiyor",
    "not accepting responses", "no longer accepting responses",
    "this form is closed", "form is closed"
]
OPEN_MARKERS = ["gönder", "yanıt gönder", "submit", "send"]

def send_email(subject: str, body: str):
    if not all([EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASS, EMAIL_TO]):
        print("E-posta ayarları eksik, e-posta gönderilmeyecek.", file=sys.stderr)
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Date"] = formatdate(localtime=True)

    try:
        if EMAIL_USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT, context=context, timeout=30) as s:
                s.login(EMAIL_USER, EMAIL_PASS)
                s.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        else:
            with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=30) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(EMAIL_USER, EMAIL_PASS)
                s.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        print("E-posta bildirimi gönderildi.")
        return True
    except Exception as e:
        print("E-posta gönderim hatası:", e, file=sys.stderr)
        return False

async def check_once():
    if not FORM_URL:
        print("HATA: FORM_URL env değişkeni gerekli!", file=sys.stderr)
        sys.exit(2)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(locale="tr-TR")
        page = await ctx.new_page()
        try:
            resp = await page.goto(FORM_URL, wait_until="networkidle", timeout=45000)
            if not resp or resp.status >= 400:
                print("Sayfa yüklenemedi veya 400+ status.")
                return 1
            html = (await page.content()).lower()
            closed = any(m in html for m in CLOSED_MARKERS)
            has_open = any(m in html for m in OPEN_MARKERS)
            opened = (not closed) and has_open
            print("Durum:", "AÇIK" if opened else "kapalı")
            if opened:
                now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                send_email(
                    subject="Form AÇILDI bildirimi",
                    body=f"📣 Form AÇILDI!\n{FORM_URL}\nZaman damgası: {now_str}"
                )
            return 0
        finally:
            await ctx.close()
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_once())
