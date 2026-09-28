"""
Standardized prompt template for small language model (Qwen2.5-1.5B) clinical clause extraction.
Preserves exact few-shot exemplars and JSON output specification.
"""

EXTRACTION_SYSTEM_PROMPT = """Extract clinical facts from ONE sentence of a medical report.
Return ONLY JSON: {"items":[{"concept":"...","assertion":"PRESENT|ABSENT|NORMAL"}]}
Rules:
- Use only words that appear in the sentence. One item per finding or structure.
- no / not / without / no evidence of => ABSENT. normal / clear / unremarkable / within normal limits => NORMAL. Otherwise PRESENT.
- Do not output numbers or measurements. If nothing clinical, return {"items":[]}.

Sentence: No pericardial effusion is seen.
{"items":[{"concept":"pericardial effusion","assertion":"ABSENT"}]}
Sentence: Spleen is normal in size and Small calculus in the gallbladder.
{"items":[{"concept":"spleen","assertion":"NORMAL"},{"concept":"calculus in gallbladder","assertion":"PRESENT"}]}

Sentence: """


def build_prompt(sentence: str) -> str:
    """Formats a single sentence into the few-shot extraction prompt."""
    return f"{EXTRACTION_SYSTEM_PROMPT}{sentence.strip()}\n"
