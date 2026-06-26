
import os
import sys
import shutil

# Import shared automation utilities
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import automation_utils

def check_ocr_setup():
    print("🔍 Checking OCR Configuration...")
    
    # Check Python dependencies
    if automation_utils.pytesseract and automation_utils.Image:
        print("✅ Python libraries (pytesseract, Pillow) are importable.")
    else:
        print("❌ Python libraries missing. Run: pip install -r requirements.txt")
        return

    # Check System dependency
    tesseract_path = shutil.which("tesseract")
    if tesseract_path:
        print(f"✅ Tesseract binary found at: {tesseract_path}")
    else:
        print("❌ Tesseract binary NOT found.")
        print("   -> Install it via Homebrew: brew install tesseract")
        return

    print("\n🎉 OCR is ready! The automation scripts will now attempt to solve captchas automatically.")

if __name__ == "__main__":
    check_ocr_setup()
