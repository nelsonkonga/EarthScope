"""Gemini wording layer for the assistant (ported from the `nasser` branch chatbot).

The rule-based engine in `assistant.py` still decides the zone, the variables and the globe
actions, and computes every number (Mann-Kendall, Theil-Sen). Gemini only rewrites that
result as a readable, sourced answer. Without `GEMINI_API_KEY` (or on any error) the caller
keeps the rule-based text, so the assistant never depends on the network to work.
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"
TIMEOUT_SECONDS = 20.0

SYSTEM_PROMPT = {
    "fr": """Tu es l'Assistant scientifique de Terra Sense Cameroun, une plateforme du NASA Space Apps Challenge (défi 02) sur le stress hydrique des sols.
Tu t'adresses à des décideurs, des agriculteurs et des éleveurs. Sois chaleureux, clair et pédagogue, sans emojis.

Règles strictes :
1. Les chiffres viennent UNIQUEMENT du « Résultat de l'analyse » ci-dessous. N'invente aucune valeur, aucune date, aucune tendance.
2. Cite toujours la source : « Selon les données GLDAS de la visualisation… », « MODIS », « Giovanni », selon la variable.
3. Explique simplement Mann-Kendall (la tendance est-elle réelle ou due au hasard ?), la valeur p et la pente de Theil-Sen quand elles apparaissent.
4. Si on demande les conséquences, relie-les à l'agriculture (rendements, irrigation), à l'élevage (abreuvement du bétail) et aux nappes phréatiques, en précisant que c'est une interprétation générale.
5. Si l'information n'est pas dans le résultat, dis-le franchement et invite à consulter la section « À propos » de la plateforme.
6. Réponds en 2 à 5 phrases courtes, en français.""",
    "en": """You are the scientific assistant of Terra Sense Cameroun, a NASA Space Apps Challenge (challenge 02) platform about soil water stress.
You speak to decision makers, farmers and herders. Be warm, clear and educational, without emojis.

Strict rules:
1. Numbers come ONLY from the "Analysis result" below. Never invent a value, a date or a trend.
2. Always cite the source: "According to the GLDAS data in the visualisation…", "MODIS", "Giovanni", depending on the variable.
3. Explain Mann-Kendall (is the trend real or due to chance?), the p-value and the Theil-Sen slope simply when they appear.
4. When asked about consequences, relate them to agriculture (yields, irrigation), livestock (watering) and groundwater, saying it is a general interpretation.
5. If the information is not in the result, say so plainly and point to the platform's "About" section.
6. Answer in 2 to 5 short sentences, in English. The analysis result may be in French: translate it.""",
}


def _api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None


def enabled() -> bool:
    return _api_key() is not None


def rewrite(question: str, analysis: str, context: dict, locale: str = "fr", history: list[dict] | None = None) -> str | None:
    """Return Gemini's wording of `analysis`, or None to keep the rule-based text."""
    key = _api_key()
    if not key:
        return None
    language = "en" if locale == "en" else "fr"
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    facts = [f"Résultat de l'analyse (moteur statistique de la plateforme) :\n{analysis}"]
    if context.get("selectedZoneId"):
        facts.append(f"Zone sélectionnée : {context['selectedZoneId']}")
    if context.get("selectedDate"):
        facts.append(f"Date affichée : {context['selectedDate']}")
    turns = []
    for message in (history or [])[-6:]:
        role = "user" if message.get("role") == "user" else "model"
        turns.append({"role": role, "parts": [{"text": str(message.get("text", ""))[:1500]}]})
    turns.append({"role": "user", "parts": [{"text": "\n\n".join(facts) + f"\n\nQuestion : {question}"}]})
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT[language]}]},
        "contents": turns,
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 700},
    }
    try:
        response = httpx.post(
            ENDPOINT.format(model=model),
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json=body,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        candidates = response.json().get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(part.get("text", "") for part in parts).strip()
        return text or None
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as error:
        log.warning("Gemini unavailable, keeping the rule-based answer: %s", str(error)[:200])
        return None
