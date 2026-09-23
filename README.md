# Ledo Advertising Company

A responsive recreation of both language versions of the reference homepage. It uses plain HTML, CSS and JavaScript, with the original Wix image assets saved locally in `assets/`.

Run `python server.py` to serve the site and its contact form API at `http://127.0.0.1:4174/`. Japanese is the default; append `?lang=en` for English. Click a project image to enlarge it.

To enable email delivery, copy `.env.example` to `.env` and fill in the SMTP username and app password. The form sends enquiries to `MAIL_RECEIVER` (defaults to `art@ledoads.com`) and sets the visitor's email as Reply-To. SMTP credentials stay on the server and are never sent to the browser. A static-only host needs a server/API with the same `/api/contact` endpoint and SMTP configuration.
