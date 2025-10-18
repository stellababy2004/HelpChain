#!/usr/bin/env python3
"""
HelpChain PWA Icon Generator
Creates PNG icons for PWA manifest from SVG base
"""

import os
from PIL import Image, ImageDraw, ImageFont


def create_icon(size):
    """Create a HelpChain icon for the given size"""

    # Create a new image with transparent background
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Colors (HelpChain theme)
    primary_color = (25, 118, 210)  # Blue
    accent_color = (76, 175, 80)  # Green
    background_color = (255, 255, 255, 255)  # White

    # Draw background circle
    margin = size // 20
    circle_bbox = [margin, margin, size - margin, size - margin]
    draw.ellipse(circle_bbox, fill=primary_color)

    # Draw inner circle
    inner_margin = size // 6
    inner_circle_bbox = [
        inner_margin,
        inner_margin,
        size - inner_margin,
        size - inner_margin,
    ]
    draw.ellipse(inner_circle_bbox, fill=background_color)

    # Draw heart symbol in the center
    heart_size = size // 3
    heart_x = size // 2
    heart_y = size // 2

    # Simple heart shape using polygons
    heart_points = [
        (heart_x, heart_y - heart_size // 4),  # Top point
        (heart_x - heart_size // 3, heart_y - heart_size // 6),  # Left curve start
        (heart_x - heart_size // 2, heart_y + heart_size // 3),  # Left bottom
        (heart_x, heart_y + heart_size // 2),  # Bottom point
        (heart_x + heart_size // 2, heart_y + heart_size // 3),  # Right bottom
        (heart_x + heart_size // 3, heart_y - heart_size // 6),  # Right curve start
    ]

    draw.polygon(heart_points, fill=accent_color)

    # Add "HC" text for smaller icons
    if size >= 96:
        try:
            # Try to use a default font, fallback to basic if not available
            font_size = max(12, size // 8)
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        text = "HC"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = (size - text_width) // 2
        text_y = (size - text_height) // 2

        draw.text((text_x, text_y), text, fill=primary_color, font=font)

    return img


def create_all_icons():
    """Create all required icon sizes"""

    sizes = [72, 96, 128, 144, 152, 192, 384, 512]

    print("Creating HelpChain PWA icons...")
    print("Generating PNG icons in all required sizes...")
    print()

    for size in sizes:
        filename = f"icon-{size}x{size}.png"

        # Create the icon
        icon = create_icon(size)

        # Save as PNG
        icon.save(filename, "PNG")

        print(f"✓ Created icon: {filename} ({size}x{size})")

    print("\nAll icons created successfully!")
    print("\nIcon features:")
    print("- Blue circular background with white center")
    print("- Green heart symbol in the center")
    print("- 'HC' text on larger icons (96px+)")
    print("- Transparent background for PWA compatibility")


if __name__ == "__main__":
    # Change to icons directory
    icons_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(icons_dir)

    create_all_icons()
