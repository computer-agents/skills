---
name: web-search
description: Search the web for current information. Use when asked to search, look up, find, or research current information, documentation, news, APIs, technical references, or anything requiring up-to-date web data.
---

# Web Search

Search the web for current information using Google's Gemini API with grounding.

## When to Use

Use this skill when you need to:
- Find current/recent information not in your training data
- Look up documentation, APIs, or technical references
- Research topics, news, or events
- Verify facts or find authoritative sources

## Usage

Run the web search script with your query:

```bash
python3 /workspace/.claude/skills/web-search/scripts/web-search.py "your search query here"
```

## Examples

```bash
# Search for documentation
python3 /workspace/.claude/skills/web-search/scripts/web-search.py "Next.js 14 app router documentation"

# Research a topic
python3 /workspace/.claude/skills/web-search/scripts/web-search.py "latest TypeScript 5.4 features"

# Find current information
python3 /workspace/.claude/skills/web-search/scripts/web-search.py "OpenAI API pricing 2024"
```

## Output

The script returns:
- A comprehensive answer synthesized from web sources
- Source URLs for verification

## Requirements

- `GEMINI_API_KEY` environment variable must be set
- Python 3.10+ with `google-genai` package installed
