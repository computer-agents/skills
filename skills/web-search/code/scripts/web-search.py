#!/usr/bin/env python3
"""
Web Search Script using Google Gemini Interactions API

This script performs web searches using Google's Gemini model with Google Search
grounding. It uses the Interactions API which returns actual source URLs (not
Google redirect URLs), enabling proper favicon display.

Also fetches related images using Brave Search API (primary) or Google Custom
Search API (fallback) when configured.

Usage:
    python3 web-search.py "your search query"

Environment Variables:
    GEMINI_API_KEY - Required. Your Google AI API key.
    BRAVE_API_KEY - Optional. Brave Search API key for image search (recommended).
    GOOGLE_CSE_API_KEY - Optional. Google API key for image search (fallback).
    GOOGLE_CSE_CX - Optional. Google Custom Search Engine ID for image search.
"""

import argparse
import json
import os
import sys
import requests
from typing import Optional, List, Dict
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed


def load_env_file():
    """Load environment variables from .env file in workspace."""
    env_paths = [
        Path('/workspace/.env'),
        Path.cwd() / '.env',
    ]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value


# Load .env file before accessing environment variables
load_env_file()

API_BASE = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = "gemini-3-flash-preview"


def web_search(
    query: str,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    system_instruction: Optional[str] = None,
) -> dict:
    """
    Perform a web search using Gemini with Google Search grounding.

    Args:
        query: The search query
        model: Gemini model to use
        api_key: Google AI API key (uses GEMINI_API_KEY env var if not provided)
        system_instruction: Optional system instruction for the model

    Returns:
        dict: Response containing search results and model output
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Try reading from secrets file (written by container entrypoint)
        secrets_file = "/workspace/.secrets/gemini_api_key"
        if os.path.exists(secrets_file):
            with open(secrets_file, 'r') as f:
                api_key = f.read().strip()

    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    # Build request payload
    payload = {
        "model": model,
        "input": query,
        "tools": [
            {"type": "google_search"}
        ],
    }

    if system_instruction:
        payload["system_instruction"] = system_instruction
    else:
        # Default instruction for search tasks
        payload["system_instruction"] = (
            "You are a helpful research assistant. When asked to search, use the Google Search "
            "tool to find relevant information. Provide a clear, concise summary of the findings "
            "with source URLs. Focus on factual information from reliable sources."
        )

    # Make API request
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    response = requests.post(API_BASE, json=payload, headers=headers, timeout=120)
    response.raise_for_status()

    return response.json()


def extract_domain(url: str) -> str:
    """Extract domain from URL, removing www. prefix."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ''


def fetch_images_brave(
    query: str,
    num_images: int = 3,
    api_key: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Fetch images using Brave Search API.

    Args:
        query: The search query
        num_images: Number of images to fetch
        api_key: Brave API key (uses BRAVE_API_KEY env var if not provided)

    Returns:
        List of image dicts with url, thumbnail, title, source
    """
    api_key = api_key or os.environ.get("BRAVE_API_KEY")

    if not api_key:
        return []

    try:
        headers = {
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
        }
        params = {
            "q": query,
            "count": min(num_images, 20),
            "safesearch": "strict",
        }

        response = requests.get(
            "https://api.search.brave.com/res/v1/images/search",
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        images = []
        for item in data.get("results", []):
            images.append({
                "url": item.get("url", ""),
                "thumbnail": item.get("thumbnail", {}).get("src", item.get("url", "")),
                "title": item.get("title", ""),
                "source": item.get("source", ""),
            })

        return images[:num_images]
    except Exception as e:
        print(f"Brave image search failed: {e}", file=sys.stderr)
        return []


def fetch_images_google(
    query: str,
    num_images: int = 3,
    api_key: Optional[str] = None,
    cse_id: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Fetch images using Google Custom Search API.

    Args:
        query: The search query
        num_images: Number of images to fetch (max 10)
        api_key: Google API key (uses GOOGLE_CSE_API_KEY env var if not provided)
        cse_id: Custom Search Engine ID (uses GOOGLE_CSE_CX env var if not provided)

    Returns:
        List of image dicts with url, thumbnail, title, source
    """
    api_key = api_key or os.environ.get("GOOGLE_CSE_API_KEY")
    cse_id = cse_id or os.environ.get("GOOGLE_CSE_CX")

    if not api_key or not cse_id:
        return []

    try:
        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "searchType": "image",
            "num": min(num_images, 10),
            "safe": "active",
        }

        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        images = []
        for item in data.get("items", []):
            images.append({
                "url": item.get("link", ""),
                "thumbnail": item.get("image", {}).get("thumbnailLink", item.get("link", "")),
                "title": item.get("title", ""),
                "source": item.get("displayLink", ""),
            })

        return images
    except Exception as e:
        print(f"Google image search failed: {e}", file=sys.stderr)
        return []


def fetch_images(
    query: str,
    num_images: int = 3,
) -> List[Dict[str, str]]:
    """
    Fetch images using available search APIs.

    Tries Brave Search API first (recommended), falls back to Google CSE.

    Args:
        query: The search query
        num_images: Number of images to fetch

    Returns:
        List of image dicts with url, thumbnail, title, source
    """
    # Try Brave Search API first (recommended)
    if os.environ.get("BRAVE_API_KEY"):
        images = fetch_images_brave(query, num_images)
        if images:
            return images

    # Fall back to Google Custom Search API
    if os.environ.get("GOOGLE_CSE_API_KEY") and os.environ.get("GOOGLE_CSE_CX"):
        images = fetch_images_google(query, num_images)
        if images:
            return images

    return []


def extract_results(response: dict) -> dict:
    """
    Extract and format search results from the API response.

    Args:
        response: Raw API response

    Returns:
        dict: Formatted results with text summary, search results, and metadata
    """
    outputs = response.get("outputs", [])

    text_content = ""
    search_results = []

    for output in outputs:
        output_type = output.get("type")

        if output_type == "text":
            text_content += output.get("text", "")

        elif output_type == "google_search_result":
            result = output.get("result", {})
            if isinstance(result, list):
                for r in result:
                    url = r.get("url", "")
                    search_results.append({
                        "url": url,
                        "title": r.get("title", ""),
                        "snippet": r.get("rendered_content", ""),
                        "domain": extract_domain(url),
                    })
            else:
                url = result.get("url", "")
                search_results.append({
                    "url": url,
                    "title": result.get("title", ""),
                    "snippet": result.get("rendered_content", ""),
                    "domain": extract_domain(url),
                })

    return {
        "summary": text_content.strip(),
        "search_results": search_results,
        "status": response.get("status", "unknown"),
        "usage": response.get("usage", {}),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Perform web searches using Gemini with Google Search grounding"
    )
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model to use (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--system",
        metavar="INSTRUCTION",
        help="Custom system instruction for the model"
    )

    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        sys.exit(1)

    try:
        # Run text search and image search in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both tasks
            text_future = executor.submit(
                web_search,
                query=args.query,
                model=args.model,
                system_instruction=args.system,
            )
            image_future = executor.submit(
                fetch_images,
                query=args.query,
                num_images=2,
            )

            # Get results
            response = text_future.result()
            images = image_future.result()

        results = extract_results(response)

        # Output in markdown format for WebSearchLogBox parsing
        print("## Search Results\n")

        if results["summary"]:
            print(results["summary"])
            print()

        if results["search_results"]:
            print("## Sources\n")
            # Deduplicate by domain
            seen_domains = set()
            for result in results["search_results"]:
                domain = result.get("domain", "")
                if domain and domain not in seen_domains:
                    seen_domains.add(domain)
                    title = result.get("title") or domain
                    url = result.get("url", "")
                    # Output in format: - [title](url){domain}
                    print(f"- [{title}]({url}){{{domain}}}")

        # Output images section if we have any
        if images:
            print("\n## Images\n")
            for img in images:
                # Output in format: - ![title](thumbnail){url}
                title = img.get("title", "")
                thumbnail = img.get("thumbnail", "")
                url = img.get("url", "")
                print(f"- ![{title}]({thumbnail}){{{url}}}")

    except requests.exceptions.HTTPError as e:
        print(f"Error: API request failed - {e}", file=sys.stderr)
        if e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"Details: {json.dumps(error_detail, indent=2)}", file=sys.stderr)
            except:
                print(f"Response: {e.response.text[:500]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
