import os
from PIL import Image, ImageDraw

def generate_app_icon(output_dir=None):
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    
    assets_dir = os.path.join(output_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    
    ico_path = os.path.join(assets_dir, "app_icon.ico")
    png_path = os.path.join(assets_dir, "app_icon.png")

    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = []

    for size in sizes:
        w, h = size
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Background rounded rectangle (Material Dark Indigo/Blue)
        pad = max(1, int(w * 0.05))
        corner_r = int(w * 0.22)
        bg_bbox = [pad, pad, w - pad, h - pad]
        
        # Gradient effect or dark surface
        draw.rounded_rectangle(bg_bbox, radius=corner_r, fill=(26, 32, 44, 255), outline=(168, 199, 250, 255), width=max(1, int(w * 0.03)))

        # Draw Headphone headband
        center_x = w // 2
        center_y = int(h * 0.48)
        headband_r = int(w * 0.26)
        band_width = max(2, int(w * 0.07))
        
        draw.arc(
            [center_x - headband_r, center_y - headband_r, center_x + headband_r, center_y + headband_r],
            start=180, end=0,
            fill=(168, 199, 250, 255),
            width=band_width
        )

        # Draw Ear cups
        cup_w = int(w * 0.12)
        cup_h = int(h * 0.24)
        cup_r = max(2, int(cup_w * 0.4))

        # Left cup
        draw.rounded_rectangle(
            [center_x - headband_r - cup_w//2, center_y, center_x - headband_r + cup_w//2, center_y + cup_h],
            radius=cup_r,
            fill=(109, 213, 140, 255)  # Material Green
        )

        # Right cup
        draw.rounded_rectangle(
            [center_x + headband_r - cup_w//2, center_y, center_x + headband_r + cup_w//2, center_y + cup_h],
            radius=cup_r,
            fill=(109, 213, 140, 255)  # Material Green
        )

        # Audio Waves in center
        bar_w = max(1, int(w * 0.04))
        gap = max(1, int(w * 0.03))
        bar_heights = [int(h * 0.10), int(h * 0.20), int(h * 0.28), int(h * 0.18), int(h * 0.08)]
        total_bars_w = len(bar_heights) * bar_w + (len(bar_heights) - 1) * gap
        start_bx = center_x - total_bars_w // 2

        for i, bh in enumerate(bar_heights):
            bx = start_bx + i * (bar_w + gap)
            by1 = int(h * 0.52) - bh // 2
            by2 = int(h * 0.52) + bh // 2
            draw.rounded_rectangle([bx, by1, bx + bar_w, by2], radius=max(1, bar_w//2), fill=(127, 207, 255, 255))

        images.append(img)

    # Save multi-resolution ICO
    images[0].save(ico_path, format="ICO", sizes=[(im.width, im.height) for im in images])
    images[0].save(png_path, format="PNG")
    print(f"Generated icon: {ico_path} and {png_path}")
    return ico_path, png_path

if __name__ == "__main__":
    generate_app_icon()
