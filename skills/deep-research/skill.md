---
name: deep-research
description: Conduct comprehensive multi-phase research on complex topics. Use when asked to research, investigate, analyze, or create detailed reports on topics requiring multiple sources, in-depth analysis, or comprehensive coverage.
---

# Deep Research

Conduct comprehensive deep research on complex topics using Google's Deep Research agent with streaming progress updates.

## When to Use

Use this skill when you need to:
- Research complex topics requiring multiple sources
- Generate comprehensive reports with citations
- Analyze and synthesize information from various angles
- Investigate technical concepts, industry trends, or detailed questions

## Usage

Run the deep research script with your topic:

```bash
python3 /workspace/.claude/skills/deep-research/scripts/deep-research.py "your research topic"
```

Optional: Save to a specific output file:

```bash
python3 /workspace/.claude/skills/deep-research/scripts/deep-research.py "your research topic" --output report.md
```

## IMPORTANT: Wait for Completion

**Deep research takes 3-10 minutes to complete.** The script will:
1. Stream thinking/progress updates in real-time
2. Automatically retry and poll for results if needed
3. Save the final report to a file when complete

**DO NOT** interrupt or check on the research while it's running. The script handles all retries and status checking internally.

## Examples

```bash
# Research a technical topic
python3 /workspace/.claude/skills/deep-research/scripts/deep-research.py "comparison of React Server Components vs traditional SSR"

# Research with custom output
python3 /workspace/.claude/skills/deep-research/scripts/deep-research.py "AI agent architectures 2024" --output ai-agents-report.md

# Research industry trends
python3 /workspace/.claude/skills/deep-research/scripts/deep-research.py "current state of WebAssembly adoption"

# Research with extended timeout (15 minutes)
python3 /workspace/.claude/skills/deep-research/scripts/deep-research.py "complex topic" --timeout 900
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | auto-generated | Output file path |
| `--timeout` | `-t` | 600 | Maximum time in seconds (default: 10 min) |
| `--verbose` | `-v` | false | Enable verbose debug logging |
| `--system` | | none | Custom system instruction |

## Research Process

The script uses Google's Deep Research agent which:

1. **Starts an interaction**: Creates a research session with the topic
2. **Streams thinking summaries**: Real-time progress as the agent researches
3. **Delivers results**: Final report with sources and citations
4. **Auto-recovers**: Handles network issues and retries automatically

## Output

The script generates a markdown report containing:
- Comprehensive research findings
- Source URLs for verification (in Sources section)

By default, reports are saved to `/workspace/deep_research/` with auto-generated filenames.

## IMPORTANT: Enhance Reports with Images

After the research completes, you MUST enhance the report with generated images:

1. **Generate a title image** for the report header
2. **Generate 1-2 concept visualizations** for key findings
3. **Insert the images** into the report using sed

Example workflow after research completes:
```bash
# Create images directory
mkdir -p /workspace/generated_images

# Generate title image
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "professional illustration of [TOPIC], modern infographic style" --output /workspace/generated_images/title.png --aspect-ratio 16:9

# Generate concept visualization
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "diagram showing [KEY CONCEPT], infographic style" --output /workspace/generated_images/concept.png

# Insert images into report (use relative paths)
sed -i '2a\\n![Title](../generated_images/title.png)\\n' /workspace/deep_research/report.md
```

Images should be saved to `/workspace/generated_images/` and referenced with relative paths from the report.

## Streaming Events

The script outputs JSON events for real-time UI updates:
- `{"event": "start", "topic": "..."}` - Research started
- `{"event": "thinking", "summary": "..."}` - Progress update
- `{"event": "content", "text": "..."}` - Report content
- `{"event": "complete", "report_file": "...", "sources_count": N}` - Done

## Requirements

- `GEMINI_API_KEY` environment variable must be set
- Python 3.10+ with `requests` package installed

## Notes

- Research typically takes 3-10 minutes depending on topic complexity
- The script blocks until completion - do not interrupt
- Results include sources for verification
- If research fails, the script will clearly indicate this
