"""What each role is asked. Every role answers in JSON so the code, not the model, decides what happens next."""
from __future__ import annotations

import json

SYSTEM = {
    "checklist": (
        "You write grading checklists for research reports. You see only the question, never a report. "
        "Write 4 to 8 yes/no questions a careful reader would use to decide whether a report answers it fully. "
        "Each must be checkable from the report alone. Reply as JSON: {\"items\": [\"...\"]}"
    ),
    "plan": (
        "You plan research. Break the question into 2 to 4 short search questions. If gaps are listed, "
        "plan only for those gaps. Reply as JSON: {\"subquestions\": [\"...\"]}"
    ),
    "notes": (
        "You are a researcher. Read the documents and take notes that help answer the search question. "
        "Each note must copy a short exact quote from one document and give that document's id. "
        "Never add facts that are not in the quote. Reply as JSON: "
        "{\"notes\": [{\"source\": \"<doc id>\", \"quote\": \"<exact words>\", \"point\": \"<the fact in your own words>\"}]}"
    ),
    "write": (
        "You write a short research report that answers the question using only the notes. Put the source id in "
        "square brackets at the end of every factual sentence, like this: The bridge opened in 1866 [doc-id]. "
        "Use only ids that appear in the notes. If a previous report and feedback are given, fix exactly what the "
        "feedback lists: remove or correct unsupported sentences, add a source to uncited ones, and cover the open "
        "points. Keep everything else that was supported. Reply as JSON: {\"report\": \"...\"}"
    ),
    "write_from_docs": (
        "You research and write in one step. Answer the question using only the documents. Put the document id in "
        "square brackets at the end of every factual sentence, like this: The bridge opened in 1866 [doc-id]. "
        "If a previous report and feedback are given, fix exactly what the feedback lists and keep everything else "
        "that was supported. Reply as JSON: {\"report\": \"...\"}"
    ),
    "support": (
        "You check one claim against a source passage. Answer true only if the passage clearly states everything "
        "the claim says. Extra detail in the claim that the passage does not state means false. "
        "Reply as JSON: {\"supported\": true} or {\"supported\": false}"
    ),
    "check": (
        "You grade a research report against one yes/no checklist question. Answer from the report text only; "
        "do not use your own knowledge. Reply as JSON: {\"pass\": true} or {\"pass\": false}"
    ),
}


def render(role: str, payload: dict) -> tuple[str, str]:
    if role not in SYSTEM:
        raise KeyError(f"unknown role {role!r}")
    return SYSTEM[role], json.dumps(payload, ensure_ascii=False, indent=1)


def parse_json(text: str) -> dict:
    """Take the first JSON object out of a reply, tolerating code fences and chatter around it."""
    text = text.strip()
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else {}
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if c == '"' and not esc:
                    in_str = False
                esc = (c == "\\") and not esc
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        out = json.loads(text[start:i + 1])
                        return out if isinstance(out, dict) else {}
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return {}
