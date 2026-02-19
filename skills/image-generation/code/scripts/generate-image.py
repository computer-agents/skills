#!/usr/bin/env python3
"""
Image Generation & Editing Skill - Generate and edit images using Gemini 3 Pro Image.

Usage:
    # Generate from text
    python3 generate-image.py "your image description"

    # Edit an existing image
    python3 generate-image.py "add a hat to the person" --input image.png

    # Combine multiple images
    python3 generate-image.py "combine these into a scene" --input img1.png --input img2.png

    # Specify output, aspect ratio, and resolution
    python3 generate-image.py "a sunset" --output sunset.png --aspect-ratio 16:9 --resolution 2K
"""

import sys
import os
import argparse
from datetime import datetime

# Default output directory for generated images
DEFAULT_OUTPUT_DIR = "/workspace/generated_images"

def main():
    parser = argparse.ArgumentParser(description='Generate or edit images using Gemini 3 Pro Image')
    parser.add_argument('prompt', help='The image description or editing instruction')
    parser.add_argument('--output', '-o', default='generated-image.png', help='Output file path')
    parser.add_argument('--input', '-i', action='append', dest='inputs', help='Input image(s) for editing (can specify multiple)')
    parser.add_argument('--aspect-ratio', '-a', default='1:1',
                        choices=['1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9'],
                        help='Output aspect ratio (default: 1:1)')
    parser.add_argument('--resolution', '-r', default='1K',
                        choices=['1K', '2K', '4K'],
                        help='Output resolution (default: 1K). 2K and 4K available for Gemini 3 Pro.')

    args = parser.parse_args()
    prompt = args.prompt
    output_file = args.output
    input_images = args.inputs or []
    aspect_ratio = args.aspect_ratio
    resolution = args.resolution

    # If using default output name, put it in the default directory with timestamp
    if output_file == 'generated-image.png':
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create a safe filename from first 30 chars of prompt
        safe_prompt = "".join(c if c.isalnum() or c in " -_" else "_" for c in prompt[:30]).strip()
        safe_prompt = safe_prompt.replace(" ", "_")
        output_file = f"{DEFAULT_OUTPUT_DIR}/image_{timestamp}_{safe_prompt}.png"

    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("Error: google-genai package not installed. Run: pip install google-genai", file=sys.stderr)
        sys.exit(1)

    try:
        from PIL import Image
        import io
    except ImportError:
        print("Error: Pillow package not installed. Run: pip install Pillow", file=sys.stderr)
        sys.exit(1)

    # Initialize client
    client = genai.Client(api_key=api_key)

    # Build contents list
    contents = []

    # Add input images if provided (for editing/composition)
    for img_path in input_images:
        if not os.path.exists(img_path):
            print(f"Error: Input image not found: {img_path}", file=sys.stderr)
            sys.exit(1)
        try:
            img = Image.open(img_path)
            contents.append(img)
            print(f"  Added input image: {img_path}")
        except Exception as e:
            print(f"Error: Failed to load image {img_path}: {e}", file=sys.stderr)
            sys.exit(1)

    # Add the text prompt
    contents.append(prompt)

    mode = "Editing" if input_images else "Generating"
    print(f"{mode} image: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    if aspect_ratio != '1:1':
        print(f"  Aspect ratio: {aspect_ratio}")

    try:
        # Configure the request
        # Note: image_size is not supported in current SDK, only aspect_ratio works
        config = types.GenerateContentConfig(
            response_modalities=['TEXT', 'IMAGE'],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
            ),
        )

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=contents,
            config=config
        )

        if not response.candidates or len(response.candidates) == 0:
            print("Error: No candidates in response", file=sys.stderr)
            sys.exit(1)

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            print("Error: No content parts in response", file=sys.stderr)
            sys.exit(1)

        # Process response parts
        image_saved = False
        text_response = []

        for part in candidate.content.parts:
            # Check for text content
            if hasattr(part, 'text') and part.text:
                # Skip thought parts (internal reasoning)
                if hasattr(part, 'thought') and part.thought:
                    continue
                text_response.append(part.text)

            # Check for image content using as_image() method (per docs)
            if hasattr(part, 'as_image'):
                try:
                    image = part.as_image()
                    if image:
                        image.save(output_file)
                        print(f"✓ Image saved to: {output_file}")
                        print(f"  Size: {image.size[0]}x{image.size[1]}")
                        image_saved = True
                except Exception:
                    pass  # as_image() might not work, try inline_data

            # Fallback: Check for inline_data (older API style)
            if not image_saved and hasattr(part, 'inline_data') and part.inline_data:
                inline_data = part.inline_data
                if hasattr(inline_data, 'data') and inline_data.data:
                    try:
                        import base64
                        # Decode base64 image data
                        image_data = inline_data.data
                        if isinstance(image_data, str):
                            image_bytes = base64.b64decode(image_data)
                        else:
                            image_bytes = image_data

                        # Save the image
                        image = Image.open(io.BytesIO(image_bytes))
                        image.save(output_file)
                        print(f"✓ Image saved to: {output_file}")
                        print(f"  Size: {image.size[0]}x{image.size[1]}")
                        image_saved = True
                    except Exception as e:
                        print(f"Warning: Failed to process inline_data: {e}", file=sys.stderr)

        # Print any text response from the model
        if text_response:
            print("\nModel response:")
            for text in text_response:
                print(text)

        if not image_saved:
            print("Error: No image data in response", file=sys.stderr)
            if text_response:
                print("The model returned text but no image. This might be due to content policy restrictions.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error generating image: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
