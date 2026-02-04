# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

"I Hate Video" - A Flask web app that converts YouTube videos into clean, readable transcripts with AI-generated chapters and takeaways. Uses Google Gemini AI for transcript cleaning.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the web app (requires GOOGLE_API_KEY in .env or environment)
python app.py
# Opens at http://127.0.0.1:8080

# CLI usage for single video processing
python clean_podcast.py <youtube_url>
python clean_podcast.py <youtube_url> --raw-only  # Skip Gemini cleaning
python clean_podcast.py <youtube_url> -o output.md  # Custom output path
```

## Architecture

Two entry points share the core processing logic:

- **`app.py`** - Flask web server with async job processing
  - Routes: `/` (UI), `/transcribe` (POST), `/status/<job_id>`, `/download/<job_id>`, `/download/<job_id>/pdf`
  - Jobs run in background threads, results cached to `transcript_cache.json`
  - PDF generation uses fpdf2 with markdown parsing

- **`clean_podcast.py`** - CLI tool and core processing library
  - `process_video()` - Main function used by both CLI and web
  - `extract_transcript()` - Uses yt-dlp to download VTT subtitles
  - `clean_transcript_with_gemini()` - Sends transcript to Gemini for cleanup and chapter generation
  - `generate_takeaways()` - Creates 5 bullet-point summary

## Key Dependencies

- **google-genai** - Gemini AI API (model: `gemini-2.5-flash`)
- **yt-dlp** - YouTube subtitle extraction (must be installed and in PATH)
- **fpdf2** - PDF generation with markdown support
