import re
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

VERSION_RE = re.compile(r"^(?P<base_id>.+?)v(?P<version>\d+)$")


def _text(el: ET.Element, path: str) -> str | None:
    node = el.find(path)
    return node.text.strip() if node is not None and node.text else None


def parse_arxiv_id_and_version(id_url: str) -> tuple[str, int]:
    tail = id_url.rstrip("/").rsplit("/", 1)[-1]
    match = VERSION_RE.match(tail)
    if not match:
        raise ValueError(f"could not parse arXiv id/version from {id_url!r}")
    return match.group("base_id"), int(match.group("version"))


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()


def parse_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def parse_entry(entry: ET.Element) -> dict:
    id_url = _text(entry, f"{ATOM_NS}id")
    if not id_url:
        raise ValueError("entry has no <id>")
    arxiv_id, version_number = parse_arxiv_id_and_version(id_url)

    raw_title = _text(entry, f"{ATOM_NS}title")
    raw_abstract = _text(entry, f"{ATOM_NS}summary")
    if not raw_title or not raw_abstract:
        raise ValueError(f"entry {arxiv_id} is missing title or abstract")

    authors = []
    for order, author_el in enumerate(entry.findall(f"{ATOM_NS}author"), start=1):
        name = _text(author_el, f"{ATOM_NS}name")
        if name:
            authors.append({"name": name, "order": order})

    primary_category_el = entry.find(f"{ARXIV_NS}primary_category")
    primary_category = primary_category_el.get("term") if primary_category_el is not None else None
    if not primary_category:
        raise ValueError(f"entry {arxiv_id} has no primary category")

    all_categories = [c.get("term") for c in entry.findall(f"{ATOM_NS}category") if c.get("term")]
    secondary_categories = [c for c in dict.fromkeys(all_categories) if c != primary_category]

    published_raw = _text(entry, f"{ATOM_NS}published")
    updated_raw = _text(entry, f"{ATOM_NS}updated")
    if not published_raw or not updated_raw:
        raise ValueError(f"entry {arxiv_id} is missing published/updated timestamps")

    doi_el = entry.find(f"{ARXIV_NS}doi")
    doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None

    source_url = None
    pdf_url = None
    for link in entry.findall(f"{ATOM_NS}link"):
        if link.get("title") == "pdf":
            pdf_url = link.get("href")
        elif link.get("rel") == "alternate":
            source_url = link.get("href")

    return {
        "arxiv_id": arxiv_id,
        "version_number": version_number,
        "title": raw_title,
        "normalized_title": normalize_title(raw_title),
        "abstract": raw_abstract,
        "authors": authors,
        "primary_category": primary_category,
        "secondary_categories": secondary_categories,
        "published_at": parse_datetime(published_raw),
        "updated_at": parse_datetime(updated_raw),
        "doi": doi,
        "source_url": source_url,
        "pdf_url": pdf_url,
        "raw_metadata": {"xml": ET.tostring(entry, encoding="unicode")},
    }


def try_extract_arxiv_id(entry: ET.Element) -> str | None:
    """Best-effort id extraction for failure logging, used when parse_entry
    itself raises before a normal arxiv_id is available."""
    id_url = _text(entry, f"{ATOM_NS}id")
    if not id_url:
        return None
    try:
        base_id, _ = parse_arxiv_id_and_version(id_url)
        return base_id
    except ValueError:
        return None


def build_version_rows(parsed: dict) -> list[dict]:
    """Builds the paper_versions rows derivable from a single arXiv API
    response. Only the latest version's title/abstract are ever available
    from this call, so an earlier v1 row (if the paper is now past v1) is
    recorded with its known submission date only, content_verified=False.
    Intermediate versions between v1 and the latest are not observable from
    this endpoint and are intentionally not fabricated.
    """
    latest_version_number = parsed["version_number"]
    base_id = parsed["arxiv_id"]
    rows = []

    if latest_version_number > 1:
        rows.append(
            {
                "version_number": 1,
                "version_identifier": f"{base_id}v1",
                "title": None,
                "abstract": None,
                "submitted_at": parsed["published_at"],
                "content_verified": False,
                "is_latest": False,
            }
        )

    rows.append(
        {
            "version_number": latest_version_number,
            "version_identifier": f"{base_id}v{latest_version_number}",
            "title": parsed["title"],
            "abstract": parsed["abstract"],
            "submitted_at": parsed["updated_at"],
            "content_verified": True,
            "is_latest": True,
        }
    )
    return rows
