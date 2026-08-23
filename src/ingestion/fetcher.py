"""Download Groww scheme pages into data/raw/{scheme_id}/."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from src.config.settings import PROJECT_ROOT, Settings, get_settings, load_schemes

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; MF-FAQ-Bot/0.1; +https://groww.in/p/mutual-funds)"
)
HTML_FILENAME = "page.html"
METADATA_FILENAME = "fetch_meta.json"


@dataclass(frozen=True)
class FetchResult:
    scheme_id: str
    scheme_name: str
    source_url: str
    source_domain: str
    html_path: Path
    metadata_path: Path
    fetched_at: str
    status_code: int
    content_type: str | None


class FetchError(Exception):
    """Raised when a scheme page cannot be fetched or saved."""


def is_allowed_domain(url: str, allowed_domains: tuple[str, ...] | None = None) -> bool:
    """Return True if the URL host is on the Groww allowlist."""
    allowed = allowed_domains or get_settings().allowed_source_domains
    host = urlparse(url).hostname
    if not host:
        return False
    host = host.lower().removeprefix("www.")
    for domain in allowed:
        domain = domain.lower().removeprefix("*.")
        if host == domain or host.endswith(f".{domain}"):
            return True
    return False


def validate_source_url(url: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not url.startswith("https://"):
        raise FetchError(f"Only HTTPS URLs are allowed: {url}")
    if not is_allowed_domain(url, settings.allowed_source_domains):
        raise FetchError(f"URL domain not allowlisted (groww.in only): {url}")


def scheme_output_dir(scheme_id: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.raw_data_dir / scheme_id


def fetch_scheme_page(
    scheme: dict,
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> FetchResult:
    """Download one Groww scheme page and persist HTML + fetch metadata."""
    settings = settings or get_settings()
    scheme_id = scheme["scheme_id"]
    source_url = scheme["source_url"]
    validate_source_url(source_url, settings)

    out_dir = scheme_output_dir(scheme_id, settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / HTML_FILENAME
    metadata_path = out_dir / METADATA_FILENAME
    fetched_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    owns_client = client is None
    http = client or httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": DEFAULT_USER_AGENT},
    )
    try:
        response = http.get(source_url)
        response.raise_for_status()
        final_url = str(response.url)
        validate_source_url(final_url, settings)

        html_path.write_bytes(response.content)
        metadata = {
            "scheme_id": scheme_id,
            "scheme_name": scheme["scheme_name"],
            "category": scheme.get("category"),
            "source_url": source_url,
            "final_url": final_url,
            "source_domain": urlparse(final_url).hostname or "groww.in",
            "fetched_at": fetched_at,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "content_length": len(response.content),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        return FetchResult(
            scheme_id=scheme_id,
            scheme_name=scheme["scheme_name"],
            source_url=source_url,
            source_domain=metadata["source_domain"],
            html_path=html_path,
            metadata_path=metadata_path,
            fetched_at=fetched_at,
            status_code=response.status_code,
            content_type=metadata["content_type"],
        )
    except httpx.HTTPError as exc:
        raise FetchError(f"Failed to fetch {source_url}: {exc}") from exc
    finally:
        if owns_client:
            http.close()


def fetch_schemes(
    schemes: list[dict] | None = None,
    *,
    scheme_ids: set[str] | None = None,
    settings: Settings | None = None,
) -> list[FetchResult]:
    """Fetch one Groww page per scheme in the registry (or filtered subset)."""
    settings = settings or get_settings()
    all_schemes = schemes or load_schemes()
    if scheme_ids is not None:
        all_schemes = [s for s in all_schemes if s["scheme_id"] in scheme_ids]

    results: list[FetchResult] = []
    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": DEFAULT_USER_AGENT},
    ) as client:
        for scheme in all_schemes:
            results.append(fetch_scheme_page(scheme, settings=settings, client=client))
    return results


def load_fetch_metadata(scheme_id: str, settings: Settings | None = None) -> dict:
    """Load persisted fetch metadata for a scheme."""
    settings = settings or get_settings()
    metadata_path = scheme_output_dir(scheme_id, settings) / METADATA_FILENAME
    if not metadata_path.exists():
        raise FetchError(f"No fetch metadata found for scheme: {scheme_id}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def fetch_result_to_dict(result: FetchResult) -> dict:
    data = asdict(result)
    data["html_path"] = str(result.html_path.relative_to(PROJECT_ROOT))
    data["metadata_path"] = str(result.metadata_path.relative_to(PROJECT_ROOT))
    return data
