import sys
from io import BytesIO

import requests
from PIL import Image

sys.path.append(".")
from bot.ascii_art_runtime import ASCII_ART_MAX_LINES, _download_image_sync


def _generate_twitch_braille_true(image_bytes: bytes, width: int = 24) -> list[str]:
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGBA")

        # Determine background color based on average edge color to guess transparent PNG intention
        # For simple icons, usually white is better.
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img).convert("L")

        # Crops empty white space around the image
        from PIL import ImageChops

        inv = Image.eval(img, lambda p: 255 - p)
        bbox = inv.getbbox()
        if bbox:
            img = img.crop(bbox)

        pixel_width = width * 2
        # Braille dots are roughly 2x taller than wide in terminal
        # To avoid squashing, we adjust the aspect ratio.
        aspect_ratio = img.height / img.width
        pixel_height = int(pixel_width * aspect_ratio * 0.75)

        img = img.resize((pixel_width, pixel_height), Image.Resampling.LANCZOS)

        # Calculate dynamic threshold (average pixel value minus an offset to catch mid-tones)
        from PIL import ImageStat

        stat = ImageStat.Stat(img)
        mean = stat.mean[0]
        threshold = min(200, max(50, mean - 20))  # Darker than mean is considered "drawn"

        braille_map = [[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]]

        lines = []
        char_height = pixel_height // 4 + (1 if pixel_height % 4 != 0 else 0)

        for y in range(min(char_height, ASCII_ART_MAX_LINES)):
            line = ""
            for x in range(width):
                char_val = 0
                for dy in range(4):
                    for dx in range(2):
                        px = x * 2 + dx
                        py = y * 4 + dy
                        if px < pixel_width and py < pixel_height:
                            # if pixel is darker than threshold, add dot
                            if img.getpixel((px, py)) < threshold:
                                char_val += braille_map[dy][dx]
                # Only append non-empty characters to preserve padding
                # If char_val == 0, use standard space instead of braille empty space (helps rendering)
                if char_val == 0:
                    line += " "
                else:
                    line += chr(0x2800 + char_val)
            lines.append(line.rstrip())
        return lines
    except Exception as e:
        print(e)
        return []


def test_quality(url, name):
    print(f"\n======== TESTANDO: {name} ========")
    image_bytes = _download_image_sync(url)
    if not image_bytes:
        print("Falha no download.")
        return
    print("\n--- TWITCH TRUE BRAILLE (ASPECT + STRIP) ---")
    lines = _generate_twitch_braille_true(image_bytes, width=28)
    print("\n".join(lines))


if __name__ == "__main__":
    test_quality(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/React-icon.svg/200px-React-icon.svg.png",
        "React Logo",
    )
    test_quality(
        "https://upload.wikimedia.org/wikipedia/en/thumb/8/87/Batman_DC_Comics.png/250px-Batman_DC_Comics.png",
        "Batman Logo",
    )
    test_quality(
        "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png", "Pikachu"
    )
