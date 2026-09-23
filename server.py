import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


BASE_DIR = Path(__file__).resolve().parent


def load_local_env():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value[:1] == value[-1:] and value.startswith(("'", '"')):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def send_contact_email(data):
    username = os.getenv("MAIL_USERNAME", "").strip()
    password = os.getenv("MAIL_PASSWORD", "").strip()
    receiver = os.getenv("MAIL_RECEIVER", "art@ledoads.com").strip()
    if not username or not password or not receiver:
        raise RuntimeError("Mail service is not configured")

    surname = data["surname"]
    first_name = data["firstName"]
    email = data["email"]
    if not surname or not first_name or not email:
        raise ValueError("Please complete the required fields")
    if len(surname) > 120 or len(first_name) > 120 or len(email) > 254:
        raise ValueError("A field exceeds the allowed length")
    if parseaddr(email)[1] != email or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Please provide a valid email address")

    fields = {
        "Phone": data["phone"],
        "Company address": data["address"],
        "Company name": data["company"],
    }
    if any(len(value) > 1000 for value in fields.values()):
        raise ValueError("A field exceeds the allowed length")

    full_name = f"{first_name} {surname}".strip()
    message = EmailMessage()
    message["Subject"] = f"Website enquiry from {full_name}"
    message["From"] = username
    message["To"] = receiver
    message["Reply-To"] = email
    body = [f"Name: {full_name}", f"Email: {email}"]
    body.extend(f"{label}: {value}" for label, value in fields.items() if value)
    message.set_content("\n".join(body))

    host = os.getenv("MAIL_SERVER", "smtp.gmail.com").strip()
    port = int(os.getenv("MAIL_PORT", "587"))
    use_ssl = os.getenv("MAIL_USE_SSL", "false").lower() in {"1", "true", "yes"}
    use_tls = os.getenv("MAIL_USE_TLS", "true").lower() in {"1", "true", "yes"}
    if use_ssl and use_tls:
        raise ValueError("Choose either SMTP SSL or STARTTLS, not both")

    client_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    options = {"context": ssl.create_default_context()} if use_ssl else {}
    with client_class(host, port, timeout=20, **options) as client:
        if use_tls:
            client.starttls(context=ssl.create_default_context())
        client.login(username, password)
        client.send_message(message)


class SiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_POST(self):
        if self.path != "/api/contact":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16_384:
                self.respond(413, {"success": False})
                return
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Invalid request")
            data = {
                key: str(data.get(key, "")).strip()
                for key in ("surname", "firstName", "email", "phone", "address", "company")
            }
            send_contact_email(data)
            self.respond(200, {"success": True})
        except ValueError as error:
            status = 400 if str(error) != "Invalid request" else 400
            self.respond(status, {"success": False, "error": "invalid_request"})
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.respond(400, {"success": False, "error": "invalid_request"})
        except Exception:
            self.respond(503, {"success": False, "error": "mail_unavailable"})

    def translate_path(self, path):
        decoded_path = unquote(path).split("?", 1)[0]
        if decoded_path == "/.env" or decoded_path.startswith("/.env/"):
            return str(BASE_DIR / "__missing_env_file__")
        return super().translate_path(path)

    def respond(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        if self.path.startswith("/api/"):
            return
        super().log_message(format, *args)


if __name__ == "__main__":
    load_local_env()
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "4174"))
    server = ThreadingHTTPServer((host, port), SiteHandler)
    print(f"Serving on http://{host}:{port}")
    server.serve_forever()
