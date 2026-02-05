# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

"I Hate Video" - A Flask web app that converts Wistia videos into clean, readable transcripts with AI-generated chapters and takeaways. Uses Google Gemini AI for transcript cleaning.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the web app (requires GOOGLE_API_KEY and WISTIA_API_KEY in .env or environment)
python app.py
# Opens at http://127.0.0.1:8080

# CLI usage for single video processing
python clean_podcast.py <wistia_url>
python clean_podcast.py <wistia_url> --raw-only  # Skip Gemini cleaning
python clean_podcast.py <wistia_url> -o output.md  # Custom output path
```

## Architecture

Two entry points share the core processing logic:

- **`app.py`** - Flask web server with async job processing
  - Routes: `/` (UI), `/transcribe` (POST), `/status/<job_id>`, `/download/<job_id>`, `/download/<job_id>/pdf`
  - Jobs run in background threads, results cached to `transcript_cache.json`
  - PDF generation uses fpdf2 with markdown parsing

- **`clean_podcast.py`** - CLI tool and core processing library
  - `process_video()` - Main function used by both CLI and web
  - `extract_transcript()` - Uses Wistia Captions API to get SRT transcripts
  - `clean_transcript_with_gemini()` - Sends transcript to Gemini for cleanup and chapter generation
  - `generate_takeaways()` - Creates 5 bullet-point summary

## Key Dependencies

- **google-genai** - Gemini AI API (model: `gemini-2.5-flash`)
- **fpdf2** - PDF generation with markdown support

## Environment Variables

- `GOOGLE_API_KEY` - Google AI API key for Gemini
- `WISTIA_API_KEY` - Wistia API key for accessing video data and captions
