#!/usr/bin/env python3
"""
Multi-provider AI text extraction module.

Supports Anthropic, OpenAI, and Google AI for structured data extraction
from PDF text or any unstructured document content.

Usage:
    from ai_extract import extract_fields

    fields = extract_fields(
        text="...raw PDF text...",
        schema={
            "totalPop": "Total jail population (Average Daily Population)",
            "bookings": "Total number of bookings this month",
        },
        context="Shelby County Jail Population Report, monthly",
    )
    # Returns: {"totalPop": 2970, "bookings": 2680}

Provider selection (in order of priority):
    1. AI_PROVIDER env var ("anthropic", "openai", "google")
    2. First available API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY)
    3. Falls back to returning empty dict if no key found

Model override:
    Set AI_MODEL env var to override the default model for the active provider.
"""

import json
import os
import re
import sys
from typing import Optional

# Default models per provider
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "google": "gemini-1.5-flash",
}


def _get_provider() -> Optional[str]:
    """Determine which provider to use."""
    explicit = os.environ.get("AI_PROVIDER", "").lower()
    if explicit in DEFAULT_MODELS:
        return explicit

    # Auto-detect from available keys
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GOOGLE_API_KEY"):
        return "google"
    return None


def _build_prompt(text: str, schema: dict[str, str], context: str) -> str:
    schema_lines = "\n".join(f'  "{k}": {v}' for k, v in schema.items())
    return f"""You are a precise data extractor. Extract structured data from the document text below.

Context: {context}

Extract ONLY the following fields (return null for any field not found):
{schema_lines}

Return a single JSON object with exactly these keys. Use null (not 0) when a value is genuinely absent.
For numeric fields return integers or floats (no commas, no currency symbols).
For percentage fields return the numeric value (e.g. 45.2 not "45.2%").

Document text:
---
{text[:12000]}
---

JSON output:"""


def _parse_json_response(raw: str) -> dict:
    """Extract JSON from model response, handling markdown code fences."""
    # Strip code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    # Find first { ... } block
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        return json.loads(m.group())
    raise ValueError(f"No JSON object found in response: {raw[:200]}")


def _extract_anthropic(prompt: str, model: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json_response(msg.content[0].text)


def _extract_openai(prompt: str, model: str) -> dict:
    import openai
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def _extract_google(prompt: str, model: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    m = genai.GenerativeModel(model)
    resp = m.generate_content(prompt)
    return _parse_json_response(resp.text)


def extract_fields(
    text: str,
    schema: dict[str, str],
    context: str = "Document extraction",
    verbose: bool = True,
) -> dict:
    """
    Extract structured fields from text using an AI model.

    Returns a dict of {field_name: value}. Missing fields are None.
    Returns empty dict if no provider is available (graceful degradation).
    """
    provider = _get_provider()
    if not provider:
        if verbose:
            print("  [ai_extract] No AI provider available — skipping AI extraction")
        return {}

    model = os.environ.get("AI_MODEL", DEFAULT_MODELS[provider])
    if verbose:
        print(f"  [ai_extract] Using {provider}/{model} to extract {len(schema)} fields")

    prompt = _build_prompt(text, schema, context)

    try:
        if provider == "anthropic":
            result = _extract_anthropic(prompt, model)
        elif provider == "openai":
            result = _extract_openai(prompt, model)
        elif provider == "google":
            result = _extract_google(prompt, model)
        else:
            return {}

        # Coerce types: ensure numeric fields are numbers, not strings
        cleaned = {}
        for k, v in result.items():
            if v is None:
                cleaned[k] = None
            elif isinstance(v, str):
                # Try to convert numeric strings
                v_stripped = v.replace(",", "").replace("%", "").strip()
                try:
                    cleaned[k] = int(v_stripped) if "." not in v_stripped else float(v_stripped)
                except ValueError:
                    cleaned[k] = v
            else:
                cleaned[k] = v

        if verbose:
            found = sum(1 for v in cleaned.values() if v is not None)
            print(f"  [ai_extract] Extracted {found}/{len(schema)} fields")
        return cleaned

    except Exception as e:
        if verbose:
            print(f"  [ai_extract] Extraction failed ({provider}): {e}")
        return {}


if __name__ == "__main__":
    # Quick test / debug mode
    provider = _get_provider()
    model = os.environ.get("AI_MODEL", DEFAULT_MODELS.get(provider or "", "n/a"))
    print(f"Active provider: {provider or 'none'}")
    print(f"Active model:    {model}")
    print(f"ANTHROPIC_API_KEY: {'set' if os.environ.get('ANTHROPIC_API_KEY') else 'not set'}")
    print(f"OPENAI_API_KEY:    {'set' if os.environ.get('OPENAI_API_KEY') else 'not set'}")
    print(f"GOOGLE_API_KEY:    {'set' if os.environ.get('GOOGLE_API_KEY') else 'not set'}")
