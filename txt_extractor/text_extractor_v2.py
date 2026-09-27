import pymupdf as fitz
import re
from pathlib import Path


class MedicalReportExtractor:
    """
    Extracts and cleans text from digital medical PDF reports.

    V2 adds layout-aware extraction using word coordinates so that
    table-like content is reconstructed more naturally than with
    page.get_text("text").
    """

    def __init__(self, pdf_path):
        self.pdf_path = Path(pdf_path)

        if not self.pdf_path.exists():
            raise FileNotFoundError(
                f"PDF file not found: {self.pdf_path}"
            )

        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError("Input file must be a PDF.")

    # ---------------------------------------------------------
    # Basic text extraction
    # ---------------------------------------------------------

    def extract_pages(self):
        """
        Extract raw text from every page separately.

        This keeps the original PyMuPDF text extraction available
        as a simple fallback.
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

    # ---------------------------------------------------------
    # Layout-aware extraction
    # ---------------------------------------------------------

    def _group_words_into_lines(self, words, y_tolerance=3.0):
        """
        Groups PDF words into visual lines using their Y coordinates.

        PyMuPDF returns words as:
        (x0, y0, x1, y1, text, block_no, line_no, word_no)

        This method reconstructs lines based on physical position
        instead of relying only on the PDF's internal text blocks.
        """

        if not words:
            return []

        # Sort primarily by vertical position and then horizontally.
        words = sorted(words, key=lambda w: (w[1], w[0]))

        lines = []

        for word in words:
            x0, y0, x1, y1, text = word[:5]
            y_center = (y0 + y1) / 2

            matching_line = None

            # Find an existing line with a sufficiently similar Y position.
            for line in lines:
                if abs(y_center - line["y_center"]) <= y_tolerance:
                    matching_line = line
                    break

            if matching_line is None:
                lines.append({
                    "y_center": y_center,
                    "words": [word]
                })
            else:
                matching_line["words"].append(word)

        # Sort each line from left to right.
        for line in lines:
            line["words"].sort(key=lambda w: w[0])

        # Restore top-to-bottom ordering.
        lines.sort(key=lambda line: line["y_center"])

        return lines

    def _line_to_text(self, words):
        """
        Converts a list of positioned words into readable text.

        A small amount of spacing is inserted based on the physical
        gap between words. This helps preserve columns in tables.
        """

        if not words:
            return ""

        result = words[0][4]
        previous_x1 = words[0][2]

        for word in words[1:]:
            x0, _, _, _, text = word[:5]

            gap = x0 - previous_x1

            # Large horizontal gaps are represented with extra spaces.
            # Always preserve a word boundary. Very small gaps can
            # still occur between separately positioned PDF words.
            # Large gaps are treated as column boundaries.
            if gap > 25:
                result += " | " + text
            else:
                result += " " + text

            previous_x1 = word[2]

        return result.strip()

    def extract_layout_pages(self):
        """
        Extracts each page using word coordinates.

        Unlike page.get_text("text"), this attempts to reconstruct
        the visual reading order of the page. It is particularly
        useful for reports containing tables.
        """

        pages = []

        with fitz.open(self.pdf_path) as document:
            for page_number, page in enumerate(document, start=1):

                words = page.get_text(
                    "words",
                    sort=True
                )

                lines = self._group_words_into_lines(words)

                text_lines = []

                for line in lines:
                    text = self._line_to_text(line["words"])

                    if text:
                        text_lines.append(text)

                pages.append({
                    "page": page_number,
                    "text": "\n".join(text_lines)
                })

        return pages

    # ---------------------------------------------------------
    # Optional native table extraction
    # ---------------------------------------------------------

    def extract_tables(self):
        """
        Attempts to extract tables using PyMuPDF's native table
        detection.

        Returns:
            [
                {
                    "page": 1,
                    "tables": [
                        {
                            "rows": [...]
                        }
                    ]
                }
            ]

        If the installed PyMuPDF version does not support table
        detection, an empty list is returned.
        """

        results = []

        with fitz.open(self.pdf_path) as document:
            for page_number, page in enumerate(document, start=1):

                page_tables = []

                try:
                    finder = page.find_tables()

                    for table in finder.tables:
                        rows = table.extract()

                        cleaned_rows = []

                        for row in rows:
                            cleaned_rows.append([
                                self.clean_text(str(cell))
                                if cell is not None else ""
                                for cell in row
                            ])

                        page_tables.append({
                            "rows": cleaned_rows
                        })

                except (AttributeError, RuntimeError):
                    # Older PyMuPDF versions may not provide find_tables().
                    pass

                results.append({
                    "page": page_number,
                    "tables": page_tables
                })

        return results

    # ---------------------------------------------------------
    # Cleaning
    # ---------------------------------------------------------

    def clean_text(self, text):
        """
        Performs basic text cleaning while preserving useful
        medical-report structure.
        """

        text = text.replace("\r\n", "\n")
        text = text.replace("\r", "\n")

        # Normalize non-breaking spaces.
        text = text.replace("\u00a0", " ")

        # Remove spaces at the end of lines.
        text = re.sub(r"[ \t]+\n", "\n", text)

        # Collapse repeated spaces, but do not destroy newlines.
        text = re.sub(r"[ \t]+", " ", text)

        # Remove excessive blank lines.
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove whitespace surrounding newlines.
        text = re.sub(r" *\n *", "\n", text)

        return text.strip()

    # ---------------------------------------------------------
    # Main extraction methods
    # ---------------------------------------------------------

    def extract_clean_text(self, layout_aware=True):
        """
        Extracts and cleans the report.

        layout_aware=True uses coordinate-based extraction.
        layout_aware=False uses the original PyMuPDF extraction.
        """

        if layout_aware:
            pages = self.extract_layout_pages()
        else:
            pages = self.extract_pages()

        cleaned_pages = []

        for page in pages:
            cleaned_pages.append({
                "page": page["page"],
                "text": self.clean_text(page["text"])
            })

        return cleaned_pages

    def get_full_text(self, layout_aware=True):
        """
        Returns the complete report as a single string.
        """

        pages = self.extract_clean_text(
            layout_aware=layout_aware
        )

        full_text = []

        for page in pages:
            full_text.append(
                f"\n--- PAGE {page['page']} ---\n"
            )
            full_text.append(page["text"])

        return "\n".join(full_text).strip()

    def save_text(self, output_path, layout_aware=True):
        """
        Saves extracted text to a .txt file.
        """

        text = self.get_full_text(
            layout_aware=layout_aware
        )

        output_path = Path(output_path)

        if not output_path.is_absolute():
            output_path = Path(__file__).parent / output_path

        output_path.write_text(
            text,
            encoding="utf-8"
        )

        return output_path


# -------------------------------------------------------------
# Test / command-line execution
# -------------------------------------------------------------

if __name__ == "__main__":

    pdf_file = Path(__file__).parent / "sample_report.pdf"

    extractor = MedicalReportExtractor(pdf_file)

    text = extractor.get_full_text(
        layout_aware=True
    )

    print("\n" + "=" * 60)
    print("LAYOUT-AWARE EXTRACTED MEDICAL REPORT")
    print("=" * 60)

    print(text)

    output_file = extractor.save_text(
        "extracted_report.txt",
        layout_aware=True
    )

    print("\n" + "=" * 60)
    print(f"Saved to: {output_file}")
    print("=" * 60)
