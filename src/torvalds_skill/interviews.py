"""
interviews.py — fetch interview transcripts from configured sources

Reads data/interview_sources.json, fetches each URL, extracts text,
and saves as markdown files under data/interviews/
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


DATA = Path(__file__).parent.parent.parent / "data"
SOURCES_FILE = DATA / "interview_sources.json"
INTERVIEWS_DIR = DATA / "interviews"


class HTMLTextExtractor(HTMLParser):
    """Extract visible text from HTML, ignoring structural elements."""

    IGNORE_TAGS = {"script", "style", "nav", "footer", "header", "head", "form"}
    SIGNAL_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "div", "span"}

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower in self.IGNORE_TAGS:
            self.skip_depth += 1
        elif self.skip_depth == 0 and tag_lower in self.SIGNAL_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in self.IGNORE_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif self.skip_depth == 0 and tag_lower in self.SIGNAL_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth > 0:
            return
        text = data.strip()
        if text:
            self.text_parts.append(text)

    def get_text(self) -> str:
        """Join collected text and normalize whitespace."""
        text = "\n".join(self.text_parts)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


def fetch_url(url: str, timeout: int = 30) -> str:
    """Fetch URL content with basic headers."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; InterviewFetcher/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube video."""
    return "youtube.com/watch" in url or "youtu.be/" in url


def extract_text_from_html(html: str) -> str:
    """Extract visible text from HTML content."""
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def format_metadata_header(source: dict) -> str:
    """Format source metadata as markdown header."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# {source['title']}",
        "",
        f"**Source ID:** {source['id']}",
        f"**Date:** {source['date']}",
        f"**URL:** {source['url']}",
        f"**Source Type:** {source.get('source_type', source.get('type', 'unknown'))}",
        f"**Fetched At:** {fetched_at}",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def fetch_interview(source: dict) -> tuple[str, str] | tuple[None, str]:
    """Fetch a single interview source.

    Returns:
        (id, text_content) on success
        (None, error_message) on failure
    """
    source_id = source["id"]
    url = source["url"]

    if is_youtube_url(url):
        return None, "YouTube transcripts must be fetched manually — see data/interviews/raw/lca-2024-keynote.md"

    try:
        html = fetch_url(url)
        text = extract_text_from_html(html)

        if not text or len(text) < 100:
            return None, f"Extracted text too short ({len(text)} chars) — likely failed to parse"

        return source_id, text
    except HTTPError as e:
        return None, f"HTTP error {e.code}: {e.reason}"
    except URLError as e:
        return None, f"URL error: {e.reason}"
    except Exception as e:
        return None, f"Unexpected error: {e}"


def save_interview(source: dict, content: str):
    """Save interview content to markdown file."""
    INTERVIEWS_DIR.mkdir(parents=True, exist_ok=True)

    header = format_metadata_header(source)
    full_content = header + content

    output_path = INTERVIEWS_DIR / f"{source['id']}.md"
    output_path.write_text(full_content, encoding="utf-8")


def fetch_interviews():
    """Fetch all interviews from configured sources."""
    if not SOURCES_FILE.exists():
        print(f"error: {SOURCES_FILE} not found")
        sys.exit(1)

    sources = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))

    INTERVIEWS_DIR.mkdir(parents=True, exist_ok=True)

    success_count = 0
    error_count = 0

    for source in sources:
        source_id = source["id"]
        print(f"fetching {source_id}...", end=" ")

        result, content = fetch_interview(source)

        if result is not None:
            save_interview(source, content)
            print(f"{len(content)} chars saved")
            success_count += 1
        else:
            print(f"error: {content}")
            error_count += 1

    print(f"\n{success_count}/{len(sources)} interviews fetched successfully")
    if error_count > 0:
        print(f"{error_count} failed")


def load_interviews() -> list[dict]:
    """Load all fetched interviews from data/interviews/.

    Returns:
        List of dicts with keys: id, title, date, url, content
    """
    if not INTERVIEWS_DIR.exists():
        return []

    interviews = []

    for md_file in sorted(INTERVIEWS_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")

        lines = content.splitlines()
        if not lines:
            continue

        title = lines[0].lstrip("# ").strip()

        metadata = {}
        content_start = 0
        for i, line in enumerate(lines[1:], start=1):
            if line.startswith("**"):
                match = re.match(r"\*\*(\w+):\*\* (.+)", line)
                if match:
                    key, value = match.groups()
                    metadata[key.lower().replace(" ", "_")] = value
            elif line.startswith("---"):
                content_start = i + 1
                break

        interview_id = md_file.stem

        full_content = "\n".join(lines[content_start:]).strip()

        interviews.append({
            "id": interview_id,
            "title": metadata.get("title", title),
            "date": metadata.get("date", "unknown"),
            "url": metadata.get("url", ""),
            "content": full_content,
        })

    return interviews


if __name__ == "__main__":
    fetch_interviews()