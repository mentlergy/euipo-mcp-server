from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

from mcp.server.fastmcp import FastMCP

from euipo_mcp_server.client import EUIPOClient

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "EUIPO Trademark Search",
    instructions="Search the European Union Intellectual Property Office (EUIPO) trademark database",
)

_client: EUIPOClient | None = None


def _get_client() -> EUIPOClient:
    global _client
    if _client is None:
        _client = EUIPOClient()
    return _client


NO_CREDENTIALS_MSG = (
    "EUIPO API credentials not configured. To set up:\n"
    "1. Register (free) at https://dev.euipo.europa.eu/\n"
    "2. Create an App in the Apps section to get Client ID and Secret\n"
    "3. Subscribe to the Trademark Search API plan\n"
    "4. Set environment variables: EUIPO_CLIENT_ID and EUIPO_CLIENT_SECRET\n\n"
    "Sandbox access is approved in ~1 day. Production takes up to 1 week."
)


class TrademarkStatus(str, Enum):
    REGISTERED = "REGISTERED"
    RECEIVED = "RECEIVED"
    UNDER_EXAMINATION = "UNDER_EXAMINATION"
    APPLICATION_PUBLISHED = "APPLICATION_PUBLISHED"
    REGISTRATION_PENDING = "REGISTRATION_PENDING"
    WITHDRAWN = "WITHDRAWN"
    REFUSED = "REFUSED"
    OPPOSITION_PENDING = "OPPOSITION_PENDING"
    APPEALED = "APPEALED"
    CANCELLATION_PENDING = "CANCELLATION_PENDING"
    CANCELLED = "CANCELLED"
    SURRENDERED = "SURRENDERED"
    EXPIRED = "EXPIRED"
    ACCEPTED = "ACCEPTED"


class MarkFeature(str, Enum):
    WORD = "WORD"
    FIGURATIVE = "FIGURATIVE"
    SHAPE_3D = "SHAPE_3D"
    COLOUR = "COLOUR"
    SOUND = "SOUND"
    HOLOGRAM = "HOLOGRAM"
    POSITION = "POSITION"
    PATTERN = "PATTERN"
    MOTION = "MOTION"
    MULTIMEDIA = "MULTIMEDIA"
    OTHER = "OTHER"


def _get_verbal_element(tm: dict[str, Any]) -> str:
    spec = tm.get("wordMarkSpecification", {})
    return spec.get("verbalElement", "") if isinstance(spec, dict) else ""


def _get_applicant_names(tm: dict[str, Any]) -> str:
    applicants = tm.get("applicants", [])
    return ", ".join(a.get("name", "") for a in applicants if a.get("name"))


def _format_trademark_summary(tm: dict[str, Any]) -> str:
    lines = []
    name = _get_verbal_element(tm) or "N/A"
    app_num = tm.get("applicationNumber", "N/A")
    status = tm.get("status", "N/A")
    lines.append(f"**{name}** ({app_num}) — {status}")

    applicant = _get_applicant_names(tm)
    if applicant:
        lines.append(f"  Applicant: {applicant}")
    if tm.get("markFeature"):
        lines.append(f"  Type: {tm['markFeature']}")
    if tm.get("niceClasses"):
        classes = ", ".join(str(c) for c in tm["niceClasses"])
        lines.append(f"  Nice Classes: {classes}")
    if tm.get("applicationDate"):
        lines.append(f"  Filed: {tm['applicationDate']}")
    if tm.get("registrationDate"):
        lines.append(f"  Registered: {tm['registrationDate']}")
    if tm.get("expiryDate"):
        lines.append(f"  Expires: {tm['expiryDate']}")
    return "\n".join(lines)


def _format_trademark_detail(tm: dict[str, Any]) -> str:
    lines = []
    name = _get_verbal_element(tm) or "N/A"
    app_num = tm.get("applicationNumber", "N/A")
    status = tm.get("status", "N/A")
    lines.append(f"# {name}")
    lines.append(f"**Application Number:** {app_num}")
    lines.append(f"**Status:** {status}")

    if tm.get("markKind"):
        lines.append(f"**Kind:** {tm['markKind']}")
    if tm.get("markFeature"):
        lines.append(f"**Mark Type:** {tm['markFeature']}")
    if tm.get("markBasis"):
        lines.append(f"**Basis:** {tm['markBasis']}")

    applicant = _get_applicant_names(tm)
    if applicant:
        lines.append(f"**Applicant:** {applicant}")
    reps = tm.get("representatives", [])
    rep_names = ", ".join(r.get("name", "") for r in reps if r.get("name"))
    if rep_names:
        lines.append(f"**Representative:** {rep_names}")

    lines.append("")
    lines.append("## Dates")
    if tm.get("applicationDate"):
        lines.append(f"- Filed: {tm['applicationDate']}")
    if tm.get("registrationDate"):
        lines.append(f"- Registered: {tm['registrationDate']}")
    if tm.get("expiryDate"):
        lines.append(f"- Expires: {tm['expiryDate']}")

    if tm.get("niceClasses"):
        classes = ", ".join(str(c) for c in tm["niceClasses"])
        lines.append(f"\n## Nice Classes\n{classes}")

    gs = tm.get("goodsAndServicesDescription", tm.get("goodsAndServices", []))
    if gs:
        lines.append("\n## Goods & Services")
        for entry in gs:
            if isinstance(entry, dict):
                cls = entry.get("niceClass", entry.get("classNumber", "?"))
                desc = entry.get("description", entry.get("goodsAndServicesDescription", ""))
                lines.append(f"- **Class {cls}:** {desc}")
            else:
                lines.append(f"- {entry}")

    pubs = tm.get("publications", [])
    if pubs:
        lines.append("\n## Publications")
        for pub in pubs:
            lines.append(f"- Bulletin {pub.get('bulletinNumber', '?')} ({pub.get('publicationDate', '?')})")

    return "\n".join(lines)


@mcp.tool()
async def search_trademarks(
    query: str,
    nice_class: str | None = None,
    status: TrademarkStatus | None = None,
    mark_feature: MarkFeature | None = None,
    applicant_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 0,
    size: int = 10,
) -> str:
    """Search the EUIPO trademark database.

    Args:
        query: Trademark name to search for (supports * wildcards)
        nice_class: Nice Classification filter (1-45), comma-separated for multiple
        status: Filter by trademark status
        mark_feature: Filter by mark type (WORD, FIGURATIVE, etc.)
        applicant_name: Filter by applicant/owner name
        date_from: Filing date lower bound (YYYY-MM-DD)
        date_to: Filing date upper bound (YYYY-MM-DD)
        page: Page number (0-based)
        size: Results per page (max 50)
    """
    client = _get_client()
    if not client.has_credentials:
        return NO_CREDENTIALS_MSG

    try:
        result = await client.search_trademarks(
            query=query,
            nice_class=nice_class,
            status=status.value if status else None,
            mark_feature=mark_feature.value if mark_feature else None,
            applicant_name=applicant_name,
            date_from=date_from,
            date_to=date_to,
            page=page,
            size=min(size, 50),
        )
    except Exception as e:
        return f"Error searching EUIPO ({client.env_label}): {e}"

    trademarks = result.get("trademarks", result.get("content", []))
    total = result.get("total", result.get("totalElements", len(trademarks)))

    if not trademarks:
        return f"No trademarks found for '{query}' ({client.env_label} environment)."

    lines = [f"Found {total} trademark(s) — showing page {page + 1} ({client.env_label}):\n"]
    for tm in trademarks:
        lines.append(_format_trademark_summary(tm))
        lines.append("")

    if total > (page + 1) * size:
        lines.append(f"_More results available. Use page={page + 1} to see next page._")

    return "\n".join(lines)


@mcp.tool()
async def get_trademark(application_number: str) -> str:
    """Get full details of a specific EUIPO trademark by its application number.

    Args:
        application_number: The EUIPO application number (e.g., '018012345')
    """
    client = _get_client()
    if not client.has_credentials:
        return NO_CREDENTIALS_MSG

    try:
        result = await client.get_trademark(application_number)
    except Exception as e:
        return f"Error fetching trademark {application_number} ({client.env_label}): {e}"

    return _format_trademark_detail(result)


@mcp.tool()
async def get_trademark_image(application_number: str) -> str:
    """Get the thumbnail and full-resolution image URLs for a figurative trademark.

    Args:
        application_number: The EUIPO application number
    """
    client = _get_client()
    if not client.has_credentials:
        return NO_CREDENTIALS_MSG

    thumbnail_url = await client.get_trademark_image_url(application_number, thumbnail=True)
    full_url = await client.get_trademark_image_url(application_number, thumbnail=False)
    return (
        f"Trademark image URLs:\n"
        f"- Thumbnail: {thumbnail_url}\n"
        f"- Full resolution: {full_url}\n\n"
        "Note: These URLs require authentication headers (Bearer token + X-IBM-Client-Id) to access. "
        "The image is available for FIGURATIVE, SHAPE_3D, and other visual mark types."
    )


def _format_gs_term(term: dict[str, Any]) -> str:
    text = term.get("text", "N/A")
    cls = term.get("classNumber", "?")
    return f"- **Class {cls}:** {text}"


def _format_taxonomy_node(node: dict[str, Any], indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = "  " * indent
    text = node.get("text", "")
    cls = node.get("classNumber")
    size = node.get("itemsSize", 0)
    label = f"{prefix}- {text}"
    if cls:
        label += f" (Class {cls})"
    if size:
        label += f" [{size} terms]"
    lines.append(label)
    for child in node.get("items", []):
        lines.extend(_format_taxonomy_node(child, indent + 1))
    return lines


@mcp.tool()
async def search_goods_and_services(
    term_text: str | None = None,
    class_number: str | None = None,
    language: str = "en",
    page: int = 0,
    size: int = 10,
) -> str:
    """Search the EUIPO Goods and Services (TMClass) database for harmonised terms.

    Args:
        term_text: Text to search for (e.g., 'clothing', 'software')
        class_number: Nice class number(s) to filter by (1-45), comma-separated
        language: Language code (default: en). Supported: bg,cs,da,de,el,en,es,et,fi,fr,hr,hu,it,lt,lv,mt,nl,pl,pt,ro,sk,sl,sv
        page: Page number (0-based)
        size: Results per page (max 100)
    """
    client = _get_client()
    if not client.has_credentials:
        return NO_CREDENTIALS_MSG

    try:
        result = await client.search_gs_terms(
            language=language,
            term_text=term_text,
            class_number=class_number,
            page=page,
            size=min(size, 100),
        )
    except Exception as e:
        return f"Error searching Goods & Services ({client.env_label}): {e}"

    terms = result.get("terms", [])
    total = result.get("totalElements", len(terms))

    if not terms:
        desc = term_text or f"class {class_number}" if class_number else "all"
        return f"No terms found for '{desc}' ({client.env_label})."

    lines = [f"Found {total} term(s) — page {page + 1} ({client.env_label}):\n"]
    for term in terms:
        lines.append(_format_gs_term(term))

    if total > (page + 1) * max(size, 10):
        lines.append(f"\n_More results available. Use page={page + 1} to see next page._")

    return "\n".join(lines)


@mcp.tool()
async def get_nice_class_headings(language: str = "en") -> str:
    """Get the headings for all 45 Nice Classification classes.

    Args:
        language: Language code (default: en)
    """
    client = _get_client()
    if not client.has_credentials:
        return NO_CREDENTIALS_MSG

    try:
        result = await client.get_gs_class_headings(language=language)
    except Exception as e:
        return f"Error fetching class headings ({client.env_label}): {e}"

    headings = result.get("headings", [])
    if not headings:
        return "No class headings returned."

    lines = [f"## Nice Classification — {len(headings)} classes ({client.env_label})\n"]
    for h in headings:
        lines.append(f"**Class {h['classNumber']}:** {h['heading']}\n")

    return "\n".join(lines)


@mcp.tool()
async def get_nice_taxonomy(
    term_text: str | None = None,
    language: str = "en",
) -> str:
    """Browse the Nice Classification taxonomy tree. Optionally filter by term text.

    Args:
        term_text: Text to filter taxonomy nodes (e.g., 'software')
        language: Language code (default: en)
    """
    client = _get_client()
    if not client.has_credentials:
        return NO_CREDENTIALS_MSG

    try:
        result = await client.get_gs_taxonomy(language=language, term_text=term_text)
    except Exception as e:
        return f"Error fetching taxonomy ({client.env_label}): {e}"

    lines = _format_taxonomy_node(result)
    header = "## Nice Classification Taxonomy"
    if term_text:
        header += f" (filtered: '{term_text}')"
    header += f" ({client.env_label})\n"

    return header + "\n".join(lines)


@mcp.tool()
async def suggest_goods_and_services(
    text: str,
    language: str = "en",
    class_number: int | None = None,
    max_suggestions: int = 20,
) -> str:
    """Get suggested harmonised terms for a free-text product/service description.

    Args:
        text: Free-text description (e.g., 'smartphone accessories')
        language: Language code (default: en)
        class_number: Optional Nice class to filter suggestions (1-45)
        max_suggestions: Maximum suggestions to return (default: 20, max: 200)
    """
    client = _get_client()
    if not client.has_credentials:
        return NO_CREDENTIALS_MSG

    try:
        result = await client.suggest_gs_terms(
            language=language,
            texts=[text],
            class_number=class_number,
            max_suggestions=max_suggestions,
        )
    except Exception as e:
        return f"Error getting suggestions ({client.env_label}): {e}"

    suggestions = result.get("suggestions", [])
    if not suggestions or not suggestions[0].get("suggestedTerms"):
        return f"No suggestions found for '{text}' ({client.env_label})."

    entry = suggestions[0]
    terms = entry.get("suggestedTerms", [])
    lines = [f"Suggestions for '{entry.get('sourceTerm', text)}' ({client.env_label}):\n"]
    for term in terms:
        lines.append(_format_gs_term(term))

    return "\n".join(lines)


@mcp.tool()
async def validate_classification(
    language: str,
    goods_and_services: str,
) -> str:
    """Validate goods & services terms against the EUIPO harmonised database (HDB).

    Checks whether terms are valid HDB entries for the specified classes.

    Args:
        language: Source language code (e.g., 'en', 'fr', 'de')
        goods_and_services: JSON array of objects with classNumber and terms. Example: [{"classNumber": 25, "terms": ["clothing", "footwear"]}]
    """
    client = _get_client()
    if not client.has_credentials:
        return NO_CREDENTIALS_MSG

    try:
        gs = json.loads(goods_and_services)
    except json.JSONDecodeError as e:
        return f"Invalid JSON for goods_and_services: {e}"

    try:
        result = await client.validate_gs_classification(language=language, goods_and_services=gs)
    except Exception as e:
        return f"Error validating classification ({client.env_label}): {e}"

    validations = result.get("goodsAndServices", result.get("validations", []))
    if not validations:
        return json.dumps(result, indent=2)

    lines = [f"## Validation Results ({client.env_label})\n"]
    for entry in validations:
        cls = entry.get("classNumber", entry.get("niceClass", "?"))
        lines.append(f"### Class {cls}")
        for term in entry.get("terms", []):
            text = term.get("text", term.get("term", "?"))
            status = term.get("status", term.get("validationStatus", "?"))
            lines.append(f"- **{text}**: {status}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def translate_classification(
    source_language: str,
    target_languages: str,
    goods_and_services: str,
) -> str:
    """Translate goods & services terms between EU languages using the EUIPO harmonised database.

    Args:
        source_language: Source language code (e.g., 'en')
        target_languages: Comma-separated target language codes (e.g., 'fr,de,es')
        goods_and_services: JSON array of objects with classNumber and terms. Example: [{"classNumber": 25, "terms": ["clothing", "footwear"]}]
    """
    client = _get_client()
    if not client.has_credentials:
        return NO_CREDENTIALS_MSG

    try:
        gs = json.loads(goods_and_services)
    except json.JSONDecodeError as e:
        return f"Invalid JSON for goods_and_services: {e}"

    langs = [l.strip() for l in target_languages.split(",")]

    try:
        result = await client.translate_gs_classification(
            source_language=source_language,
            target_languages=langs,
            goods_and_services=gs,
        )
    except Exception as e:
        return f"Error translating classification ({client.env_label}): {e}"

    translations = result.get("translations", result.get("goodsAndServices", []))
    if not translations:
        return json.dumps(result, indent=2)

    lines = [f"## Translation Results ({client.env_label})\n"]
    lines.append(f"Source: **{source_language}** → Target: **{', '.join(langs)}**\n")

    for entry in translations:
        lang = entry.get("language", "?")
        lines.append(f"### {lang.upper()}")
        for gs_entry in entry.get("goodsAndServices", []):
            cls = gs_entry.get("classNumber", "?")
            lines.append(f"**Class {cls}:**")
            for term in gs_entry.get("terms", []):
                text = term.get("text", term.get("term", "?"))
                lines.append(f"- {text}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    mcp.run(transport="stdio")
