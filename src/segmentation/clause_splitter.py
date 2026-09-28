"""
Clinical clause splitter.
Partitions sentences and paragraphs into atomic clinical statements,
preserving numbers, decimals, ranges, and abbreviations intact.
"""

import re
from typing import List

# Common medical abbreviations that should not trigger sentence boundaries
ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "vs", "eg", "ie", "approx", "s/o", "b/l", "e/o", "h/o", "n/h/o",
    "vol", "d", "no", "rt", "lt", "r", "l", "pt", "adv"
}

# Regex to protect decimals and abbreviations
DECIMAL_PROTECT = re.compile(r"(\d+)\.(\d+)")
ABBR_PROTECT = re.compile(r"\b(" + "|".join(ABBREVIATIONS) + r")\.", re.IGNORECASE)

# Coordinating conjunctions or punctuation preceding clinical assertion cues
CLAUSE_BOUNDARY = re.compile(
    r"(?:;\s*|\n+|\s*[-–—•*]\s*|\s*,\s*(?=(?:no|not|normal|unremarkable|with|without|mild|moderate|severe|grade|shows|showing)\b)|\s+(?:and|but)\s+(?=(?:no|not|without|normal|unremarkable)\b))",
    re.IGNORECASE
)


class ClauseSplitter:
    """Splits complex medical text into atomic clinical clauses."""

    @classmethod
    def split(cls, text: str) -> List[str]:
        if not text:
            return []

        # 1. Clean markdown and excessive spaces
        cleaned = re.sub(r"[*_~`#]", " ", text)
        cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()

        # 2. Split into sentences first
        sentences = cls._split_into_sentences(cleaned)

        # 3. Split each sentence into atomic clauses
        clauses: List[str] = []
        for sent in sentences:
            sent_clauses = cls._split_sentence_into_clauses(sent)
            clauses.extend(sent_clauses)

        return [c for c in clauses if c]

    @classmethod
    def _split_into_sentences(cls, text: str) -> List[str]:
        # Handle decimal numbers and known abbreviations by temporarily substituting periods
        placeholder = "___DOT___"
        protected = DECIMAL_PROTECT.sub(rf"\1{placeholder}\2", text)

        for abbr in ABBREVIATIONS:
            pat = re.compile(rf"\b({abbr})\.", re.IGNORECASE)
            protected = pat.sub(rf"\1{placeholder}", protected)

        # Split on sentence ending periods, question marks, exclamation marks, or newlines
        sentence_end = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(•\-])|\n+")
        raw_sents = sentence_end.split(protected)

        sentences = []
        for s in raw_sents:
            restored = s.replace(placeholder, ".").strip(" \t\n\r")
            if restored:
                sentences.append(restored)

        return sentences

    @classmethod
    def _split_sentence_into_clauses(cls, sentence: str) -> List[str]:
        # If sentence is already brief or contains table measurement syntax, keep intact
        if re.search(r"\b\d+(?:\.\d+)?\b.*\b\(\d+-\d+[a-zA-Z%]*\)", sentence):
            return [sentence.strip()]

        raw_chunks = CLAUSE_BOUNDARY.split(sentence)
        chunks: List[str] = []

        for chunk in raw_chunks:
            c = chunk.strip(" \t,;.-")
            if c and len(c) > 1:
                # Filter out pure numbering prefixes (e.g. "1", "2.")
                if re.match(r"^\d+\.?$", c):
                    continue
                chunks.append(c)

        return chunks if chunks else [sentence.strip()]
