from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os

from api.routes import router

app = FastAPI(title="SentinelFlow Command Center", version="2.4.0")

# Enable CORS for frontend fetches
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up templates
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates_dir = os.path.join(base_dir, "frontend", "templates")

# We will just read the HTML files and serve them as HTML responses 
# since Jinja2 expects specific formatting that might break with raw Tailwind HTML.
# But Jinja2 is fine if the HTML is standard.
try:
    templates = Jinja2Templates(directory=templates_dir)
except Exception:
    pass

# Include API routes
app.include_router(router, prefix="/api/v1")

def get_html_content(filename: str):
    filepath = os.path.join(templates_dir, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return f"<h1>404 - {filename} Not Found</h1>"

@app.get("/", response_class=HTMLResponse)
async def index():
    return get_html_content("index.html")

@app.get("/triage", response_class=HTMLResponse)
async def triage():
    return get_html_content("triage.html")

@app.get("/investigation", response_class=HTMLResponse)
async def investigation():
    return get_html_content("investigation.html")

@app.get("/entity_profile", response_class=HTMLResponse)
async def entity_profile():
    return get_html_content("entity_profile.html")
