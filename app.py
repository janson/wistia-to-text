#!/usr/bin/env python3
"""
Podcast Cleaner Web App
Flask web interface for transcribing and cleaning Wistia videos.
"""

import json
import os
import threading
import uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response

from clean_podcast import process_video, extract_video_id

app = Flask(__name__)

# Store jobs in memory (for simplicity)
jobs = {}

# Persistent cache file
CACHE_FILE = Path(__file__).parent / "transcript_cache.json"

def load_cache():
    """Load transcript cache from disk."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    """Save transcript cache to disk."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

# Cache completed transcripts by video ID
transcript_cache = load_cache()


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/transcribe", methods=["POST"])
def transcribe():
    """Start a transcription job."""
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400

    # Extract video ID and check cache
    try:
        video_id = extract_video_id(url)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # If we have a cached result, return it immediately
    if video_id in transcript_cache:
        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            "status": "completed",
            "progress": "Loaded from cache",
            "result": transcript_cache[video_id],
            "error": None,
        }
        return jsonify({"job_id": job_id})

    # Get API keys from environment
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    wistia_api_key = os.environ.get("WISTIA_API_KEY")

    if not google_api_key:
        return jsonify({"error": "GOOGLE_API_KEY not configured"}), 500
    if not wistia_api_key:
        return jsonify({"error": "WISTIA_API_KEY not configured"}), 500

    # Create job
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "processing",
        "progress": "Starting...",
        "result": None,
        "error": None,
    }

    # Run in background thread
    def run_job():
        try:
            def progress_callback(message):
                jobs[job_id]["progress"] = message

            result = process_video(url, google_api_key, progress_callback, wistia_api_key=wistia_api_key)
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["result"] = result
            # Cache the result and save to disk
            transcript_cache[video_id] = result
            save_cache(transcript_cache)
        except Exception as e:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(e)

    thread = threading.Thread(target=run_job)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    """Check job status."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    response = {
        "status": job["status"],
        "progress": job["progress"],
    }

    if job["status"] == "completed":
        response["result"] = {
            "title": job["result"]["title"],
            "markdown": job["result"]["markdown"],
            "filename": job["result"]["filename"],
        }
    elif job["status"] == "error":
        response["error"] = job["error"]

    return jsonify(response)


@app.route("/download/<job_id>")
def download(job_id):
    """Download the transcript as a markdown file."""
    from urllib.parse import quote

    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job["status"] != "completed":
        return jsonify({"error": "Job not completed"}), 400

    result = job["result"]
    # Use ASCII-safe filename and UTF-8 encoded filename for broader compatibility
    safe_filename = result["filename"].encode("ascii", "ignore").decode()
    if not safe_filename:
        safe_filename = "transcript.md"

    # URL-encode the filename for the filename* parameter (RFC 5987)
    encoded_filename = quote(result["filename"], safe='')

    return Response(
        result["markdown"],
        mimetype="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename=\"{safe_filename}\"; filename*=UTF-8''{encoded_filename}"
        },
    )


@app.route("/download/<job_id>/pdf")
def download_pdf(job_id):
    """Download the transcript as a PDF file."""
    from urllib.parse import quote
    from urllib.request import urlopen
    from fpdf import FPDF
    import io
    import re
    import tempfile

    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job["status"] != "completed":
        return jsonify({"error": "Job not completed"}), 400

    result = job["result"]

    # Get font from query parameter, default to Times New Roman
    font = request.args.get("font", "Times New Roman")
    allowed_fonts = ["Arial", "Comic Sans MS", "Georgia", "Tahoma", "Times New Roman", "Wingdings"]
    if font not in allowed_fonts:
        font = "Times New Roman"

    # Map user fonts to PDF standard fonts
    font_map = {
        "Arial": "Helvetica",
        "Comic Sans MS": "Helvetica",
        "Georgia": "Times",
        "Tahoma": "Helvetica",
        "Times New Roman": "Times",
        "Wingdings": "Helvetica",
    }
    pdf_font = font_map.get(font, "Times")

    # Get zoom level, default to 100%
    try:
        zoom = int(request.args.get("zoom", 100))
        zoom = max(50, min(200, zoom))  # Clamp between 50-200%
    except ValueError:
        zoom = 100

    # Calculate font sizes based on zoom (in points)
    base_size_pt = 12 * zoom / 100
    h1_size_pt = 18 * zoom / 100
    h2_size_pt = 14 * zoom / 100
    # Ensure minimum sizes
    base_size_pt = max(8, base_size_pt)
    h1_size_pt = max(12, h1_size_pt)
    h2_size_pt = max(10, h2_size_pt)

    # Line height multiplier (1.15 like Word default)
    line_mult = 1.15
    # Convert points to mm for line height (1 pt = 0.3528 mm)
    pt_to_mm = 0.3528
    base_line = base_size_pt * line_mult * pt_to_mm
    h1_line = h1_size_pt * line_mult * pt_to_mm
    h2_line = h2_size_pt * line_mult * pt_to_mm

    # Create PDF (Letter size: 215.9 x 279.4 mm)
    pdf = FPDF(orientation='P', unit='mm', format='Letter')
    pdf.set_margins(25, 25, 25)
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()
    pdf.set_font(pdf_font, '', base_size_pt)

    # Helper to sanitize text for PDF (latin-1 compatible)
    def sanitize(t):
        return t.encode('latin-1', 'replace').decode('latin-1')

    # Parse markdown and add to PDF
    md_content = result["markdown"]
    lines = md_content.split('\n')

    for line in lines:
        line = line.rstrip()

        # Image line - download and embed
        if line.startswith('!['):
            match = re.match(r'!\[.*?\]\((.+?)\)', line)
            if match:
                img_url = match.group(1)
                try:
                    with urlopen(img_url, timeout=10) as response:
                        img_data = response.read()
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                        tmp.write(img_data)
                        tmp_path = tmp.name
                    # Add image centered, max width 100mm
                    page_width = pdf.epw
                    img_width = min(100, page_width * 0.6)
                    x_pos = (pdf.w - img_width) / 2
                    pdf.image(tmp_path, x=x_pos, w=img_width)
                    pdf.ln(base_line)
                    os.unlink(tmp_path)
                except Exception:
                    pass  # Skip image if download fails
            continue

        # H1 header
        if line.startswith('# '):
            pdf.set_font(pdf_font, 'B', h1_size_pt)
            pdf.multi_cell(0, h1_line, sanitize(line[2:]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(base_line * 0.5)
            pdf.set_font(pdf_font, '', base_size_pt)
        # H2 header
        elif line.startswith('## '):
            pdf.ln(base_line)
            pdf.set_font(pdf_font, 'B', h2_size_pt)
            pdf.multi_cell(0, h2_line, sanitize(line[3:]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(base_line * 0.3)
            pdf.set_font(pdf_font, '', base_size_pt)
        # H3 header (chapter titles)
        elif line.startswith('### '):
            pdf.ln(base_line * 0.5)
            pdf.set_font(pdf_font, 'B', base_size_pt)
            pdf.multi_cell(0, base_line, sanitize(line[4:]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(base_line * 0.3)
            pdf.set_font(pdf_font, '', base_size_pt)
        # Horizontal rule
        elif line.strip() == '---':
            pdf.ln(base_line * 0.5)
            y = pdf.get_y()
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(base_line * 0.5)
        # Bullet point
        elif line.lstrip().startswith('* ') or line.lstrip().startswith('- '):
            text = line.lstrip()
            if text.startswith('* '):
                text = text[2:]
            elif text.startswith('- '):
                text = text[2:]
            text = text.lstrip()
            # Add bullet with indent, preserve bold markdown
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, base_line, f"- {sanitize(text)}", new_x="LMARGIN", new_y="NEXT", markdown=True)
        # Regular paragraph
        elif line.strip():
            text = line
            # Handle links - keep link text only
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
            # Use markdown=True to render **bold** text
            pdf.multi_cell(0, base_line, sanitize(text), new_x="LMARGIN", new_y="NEXT", markdown=True)
        # Empty line - small gap
        else:
            pdf.ln(base_line * 0.5)

    # Output PDF to buffer
    pdf_buffer = io.BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    # Filename handling
    pdf_filename = result["filename"].replace(".md", ".pdf")
    safe_filename = pdf_filename.encode("ascii", "ignore").decode()
    if not safe_filename:
        safe_filename = "transcript.pdf"
    encoded_filename = quote(pdf_filename, safe='')

    return Response(
        pdf_buffer.read(),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{safe_filename}\"; filename*=UTF-8''{encoded_filename}"
        },
    )


if __name__ == "__main__":
    # Load .env file if it exists
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value

    print("Starting Wistia Transcript Cleaner Web App...")
    print("Open http://127.0.0.1:8080 in your browser")
    print("Required env vars: GOOGLE_API_KEY, WISTIA_API_KEY")
    app.run(debug=True, host="0.0.0.0", port=8080)
