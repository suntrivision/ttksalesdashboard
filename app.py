"""Vercel entrypoint — redirects to the Streamlit app hosted on Streamlit Cloud."""

import os

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="TTK Sales Dashboard")

STREAMLIT_APP_URL = os.environ.get("STREAMLIT_APP_URL", "").strip()

SETUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TTK Sales Dashboard</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 640px; margin: 4rem auto; padding: 0 1.5rem; color: #1a202c; }
    h1 { font-size: 1.5rem; }
    code { background: #edf2f7; padding: 0.15rem 0.4rem; border-radius: 4px; }
    a { color: #2563eb; }
  </style>
</head>
<body>
  <h1>TTK Sales Dashboard</h1>
  <p>This Vercel project is a gateway to the Streamlit dashboard.</p>
  <ol>
    <li>Deploy the app on <a href="https://share.streamlit.io">Streamlit Community Cloud</a>
        using <code>streamlit_app.py</code> from this repo.</li>
    <li>In Vercel → Project Settings → Environment Variables, set
        <code>STREAMLIT_APP_URL</code> to your Streamlit app URL
        (e.g. <code>https://ttksalesdashboard.streamlit.app</code>).</li>
    <li>Redeploy this Vercel project.</li>
  </ol>
</body>
</html>"""


@app.get("/", response_model=None)
def home() -> Response:
    if STREAMLIT_APP_URL:
        return RedirectResponse(url=STREAMLIT_APP_URL, status_code=307)
    return HTMLResponse(SETUP_HTML)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
