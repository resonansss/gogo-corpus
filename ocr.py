"""OCR — optical character recognition — for *Gogo Reading Book* (1901)"""

import os
from pathlib import Path
import shutil
import sys
import tempfile

import ocrmypdf

ROOT = Path(__file__).resolve().parent
BOOK = ROOT / "data/reading_book_1901"

LANGUAGE = "eng" # "eng" selects a Tesseract model, not a translation for Gogo language.
DESKEW = True
PAGE_SEGMENTATION_MODE = 3


def configure_tesseract():
    if not shutil.which("tesseract"):
        for directory in (ROOT / ".tools/tesseract", Path("C:/Program Files/Tesseract-OCR")):
            if (directory / "tesseract.exe").is_file():
                os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
                break
    if not shutil.which("tesseract"):
        raise FileNotFoundError("Tesseract is missing.")


def main():
    source = BOOK / "raw/reading_book_1901.pdf"
    output_pdf = BOOK / "ocr/reading_book_1901.pdf"
    output_text = BOOK / "ocr/reading_book_1901.txt"
    try:
        if not source.is_file():
            raise FileNotFoundError(f"PDF not found: {source}")
        for path in (output_pdf, output_text):
            if path.exists():
                raise FileExistsError(f"Output already exists: {path}.")
        configure_tesseract()
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        
        with tempfile.TemporaryDirectory(prefix="ocr-", dir=output_pdf.parent) as working:
            working = Path(working)
            print("Recognizing...", flush=True)
            ocrmypdf.ocr(
                source, working / "book.pdf",
                sidecar=working / "book.txt",
                language=[LANGUAGE],
                deskew=DESKEW,
                tesseract_pagesegmode=PAGE_SEGMENTATION_MODE,
                output_type="pdf",
                rasterizer="pypdfium",
                optimize=0,
                jobs=2,
                progress_bar=False,
                tesseract_timeout=300,
            )
            shutil.move(str(working / "book.pdf"), output_pdf)
            shutil.move(str(working / "book.txt"), output_text)
        print(f"PDF: {output_pdf}\nTXT: {output_text}")

    except (OSError, ValueError, ocrmypdf.exceptions.ExitCodeException) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
