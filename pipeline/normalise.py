import re
import unicodedata


def make_slug(text: str, existing: set[str] | None = None) -> str:
    """Convert display text to a stable URL-safe slug."""
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
        "website": contact["website"],
        "email": contact["email"],
        "telephone": contact["telephone"],
        "not_open_to_public": not_open_to_public,
    }
