from rembg import remove
from PIL import Image

def remove_background(image_path: str) -> Image.Image:
    input_image = Image.open(image_path)
    output_image = remove(input_image)
    return output_image