#!/usr/bin/env python3
"""
Podcast Transcript Cleaner
Extracts Wistia video transcripts and cleans them using Gemini Pro.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from google import genai


def extract_media_id(url: str) -> str:
    """Extract media hashed ID from various Wistia URL formats.

    Wistia URLs include:
    - https://subdomain.wistia.com/medias/abcde12345
    - https://subdomain.wi.st/medias/abcde12345
    - https://fast.wistia.net/embed/iframe/abcde12345
    - https://fast.wistia.com/embed/medias/abcde12345.m3u8
    - Raw hashed ID (10 alphanumeric characters)
    """
    patterns = [
        r'(?:wistia\.com|wi\.st)/medias/([a-zA-Z0-9]{10})',
        r'(?:wistia\.net|wistia\.com)/embed/(?:iframe|medias)/([a-zA-Z0-9]{10})',
        r'^([a-zA-Z0-9]{10})$',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise Exception(f"Could not extract Wistia media ID from URL: {url}")


# Alias for backwards compatibility
extract_video_id = extract_media_id


def get_video_info(url: str, wistia_api_key: str) -> dict:
    """Extract video title and ID from Wistia URL using Data API."""
    media_id = extract_media_id(url)

    api_url = f"https://api.wistia.com/v1/medias/{media_id}.json"
    req = urllib.request.Request(api_url)
    req.add_header("Authorization", f"Bearer {wistia_api_key}")

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            thumbnail_url = data.get("thumbnail", {}).get("url", "")
            # Convert to high-res version if available
            if thumbnail_url:
                thumbnail_url = re.sub(r'image_crop_resized=\d+x\d+', 'image_crop_resized=1280x720', thumbnail_url)
            return {
                "title": data.get("name", "Unknown Title"),
                "id": media_id,
                "thumbnail_url": thumbnail_url,
            }
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise Exception("Invalid Wistia API key")
        elif e.code == 404:
            raise Exception(f"Media not found: {media_id}")
        raise Exception(f"Failed to get video info: {e}")
    except Exception as e:
        raise Exception(f"Failed to get video info: {e}")


def parse_srt(srt_content: str) -> str:
    """Parse SRT format and extract clean text."""
    lines = srt_content.split("\n")
    text_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip sequence numbers (just digits)
        if re.match(r'^\d+$', line):
            continue
        # Skip timestamp lines (00:00:00,000 --> 00:00:00,000)
        if re.match(r'^\d{2}:\d{2}:\d{2},\d{3}\s*-->', line):
            continue
        # This is actual text content
        text_lines.append(line)

    return " ".join(text_lines)


def extract_transcript(url: str, wistia_api_key: str) -> str:
    """Extract transcript from Wistia video using Captions API."""
    media_id = extract_media_id(url)

    api_url = f"https://api.wistia.com/v1/medias/{media_id}/captions.json"
    req = urllib.request.Request(api_url)
    req.add_header("Authorization", f"Bearer {wistia_api_key}")

    try:
        with urllib.request.urlopen(req) as response:
            captions = json.loads(response.read().decode())

            if not captions:
                raise Exception("No captions/transcript found for this video")

            # Prefer English, otherwise take first available
            caption = None
            for c in captions:
                if c.get("language") == "eng":
                    caption = c
                    break
            if not caption:
                caption = captions[0]

            srt_text = caption.get("text", "")
            if not srt_text:
                raise Exception("Caption text is empty")

            return parse_srt(srt_text)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise Exception("Invalid Wistia API key")
        elif e.code == 404:
            raise Exception(f"Media not found or no captions available: {media_id}")
        raise Exception(f"Failed to get transcript: {e}")
    except Exception as e:
        raise Exception(f"No transcript found for this video: {e}")


def generate_takeaways(transcript: str, video_title: str, api_key: str) -> str:
    """Generate top 5 takeaways from the transcript using Gemini."""
    client = genai.Client(api_key=api_key)

    prompt = f"""Read this transcript for "{video_title}" and extract the top 5 takeaways.

Each takeaway should be:
- One sentence, maximum 20 words
- Crisp and clear with minimum jargon
- A key insight, announcement, or important point from the video

Return ONLY a bullet list with exactly 5 items. Do not include any intro text like "Here are the takeaways" - just the bullet points.

TRANSCRIPT:
{transcript}"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text


def clean_transcript_with_gemini(transcript: str, video_title: str, api_key: str) -> str:
    """Use Gemini Pro to clean up the transcript."""
    client = genai.Client(api_key=api_key)

    prompt = f"""Clean up this podcast transcript for "{video_title}".

Combine paragraphs from the same speaker, fix capitalization and punctuation, remove filler words like unnecessary "like"s "you know"s and "um"s, and remove repeated words. If there are names, use context clues to figure out who it is. Make sure all sentences are grammatical, but do not add new phrases/clauses/ideas of your own.

Split the transcript into natural paragraphs, where each paragraph is maximum 200 words.

For videos with multiple speakers:
- Include the bolded speaker's name and a colon before their section
- There should always be a line break between each speaker's section and the next (even if this results in short paragraphs)
- Never insert a chapter heading in the middle of a single speaker's section - only between speakers

After cleaning the transcript, add chapters to split up sections/themes. Give each chapter a bolded title and insert them into the transcript as subheaders (use ### markdown formatting). The title should be a single short sentence expressing the key takeaway of that chapter. Every chapter must contain at least 2 paragraphs.

Otherwise, modify the original substance the minimum amount. Make sure the transcript is complete and not missing chunks. Be very meticulous.

Return ONLY the cleaned transcript. Do not include any intro text like "Here's the cleaned transcript..." - just start directly with the first chapter heading and content.

TRANSCRIPT:
{transcript}"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text


def sanitize_filename(title: str) -> str:
    """Convert video title to a safe filename."""
    # Remove or replace problematic characters
    safe = re.sub(r'[<>:"/\\|?*]', "", title)
    safe = re.sub(r"\s+", "_", safe)
    return safe[:100]  # Limit length


def process_video(url: str, google_api_key: str, progress_callback=None, wistia_api_key: str = None) -> dict:
    """
    Process a Wistia video and return the cleaned transcript with takeaways.

    Args:
        url: Wistia media page URL
        google_api_key: Google AI API key for Gemini
        progress_callback: Optional callback function for progress updates
        wistia_api_key: Wistia API key for accessing video data

    Returns:
        dict with keys: title, url, takeaways, transcript, markdown, filename
    """
    if not wistia_api_key:
        raise Exception("Wistia API key is required")

    def update_progress(message):
        if progress_callback:
            progress_callback(message)

    update_progress("Getting video info...")
    info = get_video_info(url, wistia_api_key)

    update_progress("Extracting transcript...")
    raw_transcript = extract_transcript(url, wistia_api_key)

    update_progress("Cleaning transcript with Gemini...")
    transcript = clean_transcript_with_gemini(raw_transcript, info["title"], google_api_key)

    update_progress("Generating takeaways...")
    takeaways = generate_takeaways(transcript, info["title"], google_api_key)

    # Build markdown content with thumbnail from Wistia
    markdown = ""
    if info.get("thumbnail_url"):
        markdown += f"![Thumbnail]({info['thumbnail_url']})\n\n"
    markdown += f"# {info['title']}\n\n"
    markdown += f"Source: {url}\n\n"
    markdown += "## Top Takeaways\n\n"
    markdown += takeaways
    markdown += "\n\n---\n\n"
    markdown += "## Full Transcript\n\n"
    markdown += transcript

    filename = f"{sanitize_filename(info['title'])}.md"

    return {
        "title": info["title"],
        "url": url,
        "takeaways": takeaways,
        "transcript": transcript,
        "markdown": markdown,
        "filename": filename,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract and clean video transcripts from Wistia"
    )
    parser.add_argument("url", help="Wistia media page URL")
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: auto-generated from video title)",
    )
    parser.add_argument(
        "--google-api-key",
        help="Google AI API key (or set GOOGLE_API_KEY env var)",
    )
    parser.add_argument(
        "--wistia-api-key",
        help="Wistia API key (or set WISTIA_API_KEY env var)",
    )
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="Only extract raw transcript, don't clean with Gemini",
    )

    args = parser.parse_args()

    # Get API keys
    google_api_key = args.google_api_key or os.environ.get("GOOGLE_API_KEY")
    wistia_api_key = args.wistia_api_key or os.environ.get("WISTIA_API_KEY")

    if not wistia_api_key:
        print("Error: Wistia API key required. Set WISTIA_API_KEY or use --wistia-api-key")
        sys.exit(1)

    if not google_api_key and not args.raw_only:
        print("Error: Google AI API key required. Set GOOGLE_API_KEY or use --google-api-key")
        print("Get your API key at: https://aistudio.google.com/apikey")
        sys.exit(1)

    try:
        # Get video info
        print("Getting video info...")
        info = get_video_info(args.url, wistia_api_key)
        print(f"Video: {info['title']}")

        # Extract transcript
        print("Extracting transcript...")
        transcript = extract_transcript(args.url, wistia_api_key)
        print(f"Extracted {len(transcript)} characters")

        if args.raw_only:
            final_transcript = transcript
            takeaways = ""
            suffix = "_raw"
        else:
            # Clean with Gemini
            print("Cleaning transcript with Gemini...")
            final_transcript = clean_transcript_with_gemini(
                transcript, info["title"], google_api_key
            )
            # Generate takeaways
            print("Generating takeaways...")
            takeaways = generate_takeaways(final_transcript, info["title"], google_api_key)
            suffix = ""

        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            filename = f"{sanitize_filename(info['title'])}{suffix}.md"
            output_path = Path.home() / "podcast-cleaner" / "transcripts" / filename

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write output
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {info['title']}\n\n")
            f.write(f"Source: {args.url}\n\n")
            if takeaways:
                f.write("## Top Takeaways\n\n")
                f.write(takeaways)
                f.write("\n\n")
            f.write("---\n\n")
            f.write("## Full Transcript\n\n")
            f.write(final_transcript)

        print(f"\nSaved to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
