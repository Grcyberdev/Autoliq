
import sys
import os
try:
    from PIL import Image, ImageOps, ImageFilter
    import pytesseract
except ImportError:
    print("Dependencies missing. Run in virtual env.")
    sys.exit(1)

# Image path from user's upload
TEST_IMAGE_PATH = "/Users/rajdeepgrover/.gemini/antigravity/brain/260635c9-98fa-49a8-9f0a-54d1a704ca7d/uploaded_image_1766814700710.png"

def test_ocr():
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f"File not found: {TEST_IMAGE_PATH}")
        return




    print(f"Testing OCR on: {TEST_IMAGE_PATH}")
    original = Image.open(TEST_IMAGE_PATH).convert("RGB")
    
    # Test multiple scales
    for scale in [3, 4, 5]:
        print(f"\n=== Scale {scale}x (LANCZOS) ===")
        new_size = (original.width * scale, original.height * scale)
        upscaled = original.resize(new_size, Image.Resampling.LANCZOS)
        
        # Standardize: White Text on Black BG -> Invert -> Black Text on White BG
        # Let's try both polarity
        
        # 1. Straight Grayscale
        gray = ImageOps.grayscale(upscaled)
        # AutoContrast to stretch values
        gray = ImageOps.autocontrast(gray)
        
        # 2. Thresholding
        for th in [120, 140, 160]:
            thresh = gray.point(lambda p: p > th and 255)
            
            # Check if we need to invert to get Black Text on White BG.
            # Tesseract likes Black Text.
            # Count white pixels. If > 50%, it's White BG.
            # Get data locally
            pixels = list(thresh.getdata())
            white_pixels = pixels.count(255)
            if white_pixels < len(pixels) / 2:
                # Mostly black -> Text is white? Or bg is black.
                # Invert to get White BG
                thresh = ImageOps.invert(thresh)
            
            tess_config = '--psm 7 -c tessedit_char_whitelist=0123456789'
            
            base = pytesseract.image_to_string(thresh, config=tess_config).strip()
            
            # Filters (assuming Black Text on White BG)
            # MinFilter(3) = Erode White = THICKEN Black Text
            # MaxFilter(3) = Dilate White = THIN Black Text
            
            thickened = thresh.filter(ImageFilter.MinFilter(3)) # Thicker text
            thinned = thresh.filter(ImageFilter.MaxFilter(3))   # Thinner text
            
            txt_thick = pytesseract.image_to_string(thickened, config=tess_config).strip()
            txt_thin = pytesseract.image_to_string(thinned, config=tess_config).strip()

            print(f"  Th {th} | Base: '{base}' | Thicken: '{txt_thick}' | Thin: '{txt_thin}'")

if __name__ == "__main__":
    test_ocr()
