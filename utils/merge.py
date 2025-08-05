from PIL import Image

def merge_images(background_path: str, foreground_image: Image.Image) -> Image.Image:
    # Buka background dan konversi ke RGBA
    background = Image.open(background_path).convert("RGBA")

    # Resize background agar ukurannya sama dengan foreground
    background = background.resize(foreground_image.size)

    # Konversi foreground ke RGBA (pastikan ada alpha channel)
    foreground_image = foreground_image.convert("RGBA")

    # Tempelkan foreground di atas background (di posisi 0,0)
    background.paste(foreground_image, (0, 0), foreground_image)

    return background
