import cv2
import numpy as np
from PIL import Image

def apply_sepia(pil_img: Image.Image) -> Image.Image:
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2RGB)
    sepia_filter = np.array([[0.272, 0.534, 0.131],
                             [0.349, 0.686, 0.168],
                             [0.393, 0.769, 0.189]])
    sepia_img = cv2.transform(img, sepia_filter)
    sepia_img = np.clip(sepia_img, 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(sepia_img, cv2.COLOR_BGR2RGB))

def apply_blur(pil_img: Image.Image, ksize: int = 5) -> Image.Image:
    rgba = pil_img.convert("RGBA")
    r, g, b, a = rgba.split()

    rgb_image = Image.merge("RGB", (r, g, b))
    rgb_array = np.array(rgb_image)
    blurred_rgb = cv2.GaussianBlur(rgb_array, (ksize, ksize), 0)

    blurred_pil = Image.fromarray(blurred_rgb)
    result = Image.merge("RGBA", (*blurred_pil.split(), a))  # Rekombinasi alpha
    return result

def apply_sharpen(pil_img: Image.Image) -> Image.Image:
    rgba = pil_img.convert("RGBA")
    r, g, b, a = rgba.split()

    rgb_image = Image.merge("RGB", (r, g, b))
    img = np.array(rgb_image)
    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])
    sharpened = cv2.filter2D(img, -1, kernel)

    sharpened_pil = Image.fromarray(sharpened)
    result = Image.merge("RGBA", (*sharpened_pil.split(), a))  # Rekombinasi alpha
    return result

def apply_grayscale(pil_img: Image.Image) -> Image.Image:
    rgba = pil_img.convert("RGBA")
    r, g, b, a = rgba.split()

    rgb_image = Image.merge("RGB", (r, g, b))
    img = np.array(rgb_image)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

    gray_pil = Image.fromarray(gray_rgb)
    result = Image.merge("RGBA", (*gray_pil.split(), a))  # Rekombinasi alpha
    return result
