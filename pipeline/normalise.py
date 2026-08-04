import re
import unicodedata


def safe_url(url: str | None) -> str | None:
    """Accept only http/https URLs. Returns None for anything else."""
    if not url:
        return None
    url = url.strip()
    if url.startswith(("http://", "https://")):
        return url
    return None


_COMPANY_SUFFIX_RE = re.compile(
    r"\b(limited|incorporated|corporation)\b", re.I
)
_COMPANY_SUFFIX_MAP = {
    "limited": "ltd",
    "incorporated": "inc",
    "corporation": "corp",
}


def _normalise_company_name(text: str) -> str:
    """Normalise common company name variations so slugs are stable."""
    def _replace(m: re.Match) -> str:
        return _COMPANY_SUFFIX_MAP.get(m.group(0).lower(), m.group(0).lower())
    # Strip leading "The "
    text = re.sub(r"^the\s+", "", text, flags=re.I)
    text = _COMPANY_SUFFIX_RE.sub(_replace, text)
    return text


def canonical_name(text: str) -> str:
    """Return a lower-case normalised name suitable for dedup matching."""
    t = unicodedata.normalize("NFKD", text)
    t = t.encode("ascii", "ignore").decode("ascii").lower().strip()
    t = _normalise_company_name(t)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def make_slug(text: str, existing: set[str] | None = None) -> str:
    """Convert display text to a stable URL-safe slug."""
    text = _normalise_company_name(text)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    if existing and text in existing:
        i = 2
        while f"{text}-{i}" in existing:
            i += 1
        text = f"{text}-{i}"
    return text


_TEL_RE = re.compile(r"Tel:\s*([^\n]+)", re.I)
_EMAIL_RE = re.compile(r"Email:\s*([^\s\n]+@[^\s\n]+)", re.I)
_URL_RE = re.compile(r"https?://[^\s\n]+", re.I)


def extract_contact_parts(raw: str) -> dict:
    tel_m = _TEL_RE.search(raw)
    email_m = _EMAIL_RE.search(raw)
    url_m = _URL_RE.search(raw)
    return {
        "telephone": tel_m.group(1).strip() if tel_m else None,
        "email": email_m.group(1).strip() if email_m else None,
        "website": url_m.group(0).strip() if url_m else None,
    }


def normalise_provider(raw_name: str, location: str, address: str, contact_details: str,
                        not_open_to_public: bool, existing_slugs: set[str]) -> dict:
    slug = make_slug(raw_name, existing_slugs)
    existing_slugs.add(slug)
    contact = extract_contact_parts(contact_details)

    region = location.strip() if location else None
    city = None
    address_clean = address.strip() if address else None

    return {
        "id": slug,
        "official_name": raw_name.strip(),
        "alt_names": [],
        "address": address_clean,
        "city": city,
        "region": region,
        "country": "GB",
        "postcode": None,
        "lat": None,
        "lng": None,
        "website": safe_url(contact["website"]),
        "email": contact["email"],
        "telephone": contact["telephone"],
        "not_open_to_public": not_open_to_public,
    }
