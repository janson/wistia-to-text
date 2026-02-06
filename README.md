# I Hate Video

Convert Wistia videos into clean, readable transcripts with AI-generated chapters and takeaways.

Tired of talks and podcasts being video-only? This tool takes any Wistia video link and converts it to a grammatical transcript with chapters and top takeaways.

![Screenshot](i-hate-video-example.png)

## Features

- Extracts transcripts from Wistia videos
- Cleans up captions using Gemini AI
- Adds chapter headers based on content themes
- Generates top 5 takeaways with direct quotes
- Includes video thumbnail
- MS Word 2003-inspired interface
- Export as Markdown (.md) or PDF
- Font selection (Arial, Comic Sans, Georgia, Tahoma, Times New Roman, Wingdings)
- Zoom controls for adjusting text size
- Persistent cache saves results to disk

## Supported Wistia URL Formats

The following Wistia URL formats are supported:

| Format | Example |
|--------|---------|
| Media page URL | `https://yourcompany.wistia.com/medias/abcde12345` |
| Short URL | `https://yourcompany.wi.st/medias/abcde12345` |
| Iframe embed URL | `https://fast.wistia.net/embed/iframe/abcde12345` |
| HLS stream URL | `https://fast.wistia.com/embed/medias/abcde12345.m3u8` |
| Raw hashed ID | `abcde12345` |

The hashed ID is the 10-character alphanumeric string that uniquely identifies your Wistia video.

## Prerequisites

- Python 3.10+
- A Google AI API key (for Gemini)
- A Wistia API key (for accessing video data and captions)

## Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/jaswsunny/youtube-to-text.git
   cd youtube-to-text
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Get API keys**
   - Google AI API key: Go to [Google AI Studio](https://aistudio.google.com/apikey) and create an API key
   - Wistia API key: Go to your [Wistia account settings](https://my.wistia.com/account/api) to generate an API token

5. **Create a `.env` file**
   ```bash
   echo "GOOGLE_API_KEY=your_google_api_key_here" > .env
   echo "WISTIA_API_KEY=your_wistia_api_key_here" >> .env
   ```

6. **Run the app**
   ```bash
   python app.py
   ```

7. **Open in browser**
   - Go to http://127.0.0.1:8080

## Usage

1. Paste a Wistia URL into the input field
2. Click "Textify"
3. Wait for the transcript to be processed (this may take a few minutes)
4. Read the transcript in the viewer
5. Use the font dropdown and zoom controls to customize the view
6. Click "Save" and choose Markdown or PDF to download

## Notes

- Requires videos to have captions (auto-generated or manual) in Wistia
- Transcripts are cached to disk (`transcript_cache.json`) and persist across restarts

## Tech Stack

- Flask (Python web framework)
- Wistia Data API (video metadata and captions)
- Google Gemini AI (transcript cleaning)
- fpdf2 (PDF generation)
- marked.js (Markdown rendering)

## License

MIT
