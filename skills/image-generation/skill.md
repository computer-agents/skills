---
name: image-generation
description: Generate and edit images using AI. Use when asked to create, generate, draw, or edit images, illustrations, diagrams, comics, pictures, artwork, logos, or any visual content. Also use for image editing, style transfer, adding elements to photos, or combining multiple images.
---

# Image Generation & Editing

Generate and edit images using Gemini 3 Pro Image - a state-of-the-art model for professional image creation.

## When to Use

Use this skill when you need to:
- Generate images from text descriptions
- Edit existing images (add/remove/modify elements)
- Combine multiple images into new compositions
- Apply style transfers to images
- Create visual assets, illustrations, or diagrams
- Generate images with text/logos (high-fidelity text rendering)

## Usage

### Generate from Text (Text-to-Image)

```bash
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "your image description"
```

### Edit an Existing Image

```bash
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "add a wizard hat to the cat" --input cat.png
```

### Combine Multiple Images

```bash
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "create a group photo of these people" --input person1.png --input person2.png --input person3.png
```

### Specify Output Options

```bash
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "a cinematic sunset" \
  --output sunset.png \
  --aspect-ratio 16:9 \
  --resolution 2K
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | Auto-generated in `/workspace/generated_images/` | Output file path |
| `--input` | `-i` | None | Input image for editing (can specify multiple) |
| `--aspect-ratio` | `-a` | `1:1` | Output aspect ratio |
| `--resolution` | `-r` | `1K` | Output resolution (1K, 2K, or 4K) |

By default, images are saved to `/workspace/generated_images/` with timestamped filenames like `image_20250120_143052_your_prompt.png`.

### Aspect Ratios

`1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`

### Resolutions

- `1K` - ~1024px (default, fastest)
- `2K` - ~2048px (higher quality)
- `4K` - ~4096px (highest quality, slower)

## Examples

### Text-to-Image Generation

```bash
# Simple generation
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "a serene mountain landscape at sunset"

# Product mockup
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "minimalist ceramic coffee mug on polished concrete, studio lighting" --aspect-ratio 1:1

# Logo with text
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "modern minimalist logo for 'The Daily Grind' coffee shop, black and white, clean sans-serif font"

# High-resolution artwork
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "Da Vinci style anatomical sketch of a butterfly" --resolution 4K
```

### Image Editing

```bash
# Add elements
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "add a small knitted wizard hat on the cat's head" --input cat.png

# Remove/change elements (inpainting)
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "change the blue sofa to a brown leather chesterfield" --input living_room.png

# Style transfer
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "transform this into Van Gogh's Starry Night style" --input city_photo.png
```

### Multi-Image Composition

```bash
# Fashion mockup: dress + model
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "professional photo of the woman wearing the dress" --input dress.png --input model.png

# Add logo to product
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "add the logo onto the t-shirt" --input tshirt.png --input logo.png

# Group photo (up to 5 people with high fidelity)
python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "office group photo, making funny faces" --input p1.png --input p2.png --input p3.png
```

## Capabilities

### Gemini 3 Pro Image Features

- **High-resolution output**: 1K, 2K, and 4K generation
- **Advanced text rendering**: Legible, stylized text for logos, diagrams, marketing
- **Thinking mode**: Model reasons through complex prompts for better results
- **Up to 14 reference images**: Mix images for composition (5 high-fidelity people)
- **Semantic masking**: Edit specific parts without explicit masks

## Requirements

- `GEMINI_API_KEY` environment variable must be set
- Python 3.10+ with `google-genai` and `Pillow` packages installed

## Tips for Better Results

### For Generation
- **Be descriptive**: "A photorealistic close-up portrait with soft golden hour lighting" beats "a portrait"
- **Specify style**: Include art style references (minimalist, photorealistic, watercolor, etc.)
- **Add camera details**: Mention lens type, lighting setup, camera angle for photorealistic images
- **Use step-by-step**: For complex scenes, describe background first, then foreground elements

### For Editing
- **Be specific about what to preserve**: "Keep the woman's face unchanged, only add..."
- **Describe the integration**: "The hat should look naturally placed, matching the lighting"
- **Use semantic descriptions**: Instead of "mask the sofa", say "change only the sofa"

### For Text in Images
- **Specify font style descriptively**: "clean, bold, sans-serif" or "elegant script"
- **Place text explicitly**: "text at the top center of the image"
