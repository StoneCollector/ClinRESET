import pymupdf as fitz
import re
from pathlib import Path


class MedicalReportExtractor:
    """
    Extracts and cleans text from medical PDF reports.
    Designed for text-based/digital PDFs.
    """

    def __init__(self, pdf_path):
        self.pdf_path = Path(pdf_path)

        if not self.pdf_path.exists():
            raise FileNotFoundError(
                f"PDF file not found: {self.pdf_path}"
            )

        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError("Input file must be a PDF.")

    def extract_pages(self):
        """
        Extract raw text from every page separately.
        Returns a list of dictionaries containing page information.
        """

        pages = []

        with fitz.open(self.pdf_path) as document:

            for page_number, page in enumerate(document, start=1):

                text = page.get_text("text")

                pages.append({
                    "page": page_number,
                    "text": text
                })

        return pages

    def clean_text(self, text):
        """
        Performs basic text cleaning while preserving
        useful medical report structure.
        """

        # Normalize different newline characters
        text = text.replace("\r\n", "\n")
        text = text.replace("\r", "\n")

        # Remove excessive spaces
        text = re.sub(r"[ \t]+", " ", text)

        # Remove excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove spaces around newlines
        text = re.sub(r" *\n *", "\n", text)

        return text.strip()

    def extract_clean_text(self):
        """
        Extracts and cleans the complete report.
        """

        pages = self.extract_pages()

        cleaned_pages = []

        for page in pages:

            cleaned = self.clean_text(page["text"])

            cleaned_pages.append({
                "page": page["page"],
                "text": cleaned
            })

        return cleaned_pages

    def get_full_text(self):
        """
        Returns the complete report as a single string.
        """

        pages = self.extract_clean_text()

        full_text = []

        for page in pages:

            full_text.append(
                f"\n--- PAGE {page['page']} ---\n"
            )

            full_text.append(page["text"])

        return "\n".join(full_text).strip()

    def save_text(self, output_path):
        """
        Saves extracted text to a .txt file.
        """

        text = self.get_full_text()

        output_path = Path(__file__).parent / Path(output_path)

        output_path.write_text(
            text,
            encoding="utf-8"
        )

        return output_path


if __name__ == "__main__":

    # Change this to your PDF
    pdf_file = Path(__file__).parent / "sample_report.pdf"

    extractor = MedicalReportExtractor(pdf_file)

    text = extractor.get_full_text()

    print("\n" + "=" * 60)
    print("EXTRACTED MEDICAL REPORT")
    print("=" * 60)

    print(text)

    extractor.save_text("extracted_report.txt")

    print("\n" + "=" * 60)
    print("Saved to extracted_report.txt")
    print("=" * 60)