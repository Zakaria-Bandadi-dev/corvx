import json

from deep_translator import GoogleTranslator

from services.groq_client import generate_with_groq


def safe_translate(text, target_lang):
    if not text:
        return None
    try:
        text = str(text)
        if len(text) <= 4500:
            return GoogleTranslator(source="auto", target=target_lang).translate(text)

        chunks = [text[i:i + 4500] for i in range(0, len(text), 4500)]
        translated_chunks = []
        for chunk in chunks:
            translated_chunks.append(
                GoogleTranslator(source="auto", target=target_lang).translate(chunk)
            )
        return " ".join(t for t in translated_chunks if t)

    except Exception as e:
        print(f"!! deep-translator fallback failed ({target_lang}): {e}")
        return None


def translate_article(title, content, language):
    language_names = {
        "ar": "Arabic",
        "fr": "French",
        "en": "English",
        "es": "Spanish"
    }
    target = language_names.get(language, "English")

    prompt = f"""Translate this news article into {target}.

IMPORTANT:
Preserve the meaning.
Do not add information.
Do not remove information.
Keep names and numbers correct.
Write natural professional news language.

TITLE:
{title}

CONTENT:
{content}

Return ONLY JSON:
{{
"title": "...",
"content": "..."
}}
"""
    raw = generate_with_groq(prompt)
    data = None
    if raw:
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.replace("```json", "")
                clean = clean.replace("```", "")
                clean = clean.strip()
            data = json.loads(clean)
        except Exception as e:
            print(f"!! Groq translation JSON parse failed: {e}")
            data = None

    if data and data.get("title") and data.get("content"):
        return data

    print(f"!! Falling back to deep-translator for '{language}'")
    fallback_title = safe_translate(title, language)
    fallback_content = safe_translate(content, language)

    if fallback_title or fallback_content:
        return {
            "title": fallback_title or title,
            "content": fallback_content or content,
        }
    return None
