import re
import logging
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"

MCA_ATP_URL = "https://www.gov.uk/guidance/mca-approved-training-providers-atp"

# Map section heading keywords → category IDs
_HEADING_CATEGORY_MAP = [
    (re.compile(r"basic training", re.I), "stcw_basic"),
    (re.compile(r"advanced training", re.I), "stcw_advanced"),
    (re.compile(r"updating stcw|refresher", re.I), "stcw_refresher"),
    (re.compile(r"tanker", re.I), "stcw_tanker"),
    (re.compile(r"IGF", re.I), "stcw_igf"),
    (re.compile(r"HELM", re.I), "stcw_helm"),
    (re.compile(r"ECDIS|NAEST", re.I), "stcw_ecdis_naest"),
    (re.compile(r"GMDSS|radio|operators certificate", re.I), "gmdss"),
    (re.compile(r"high voltage", re.I), "high_voltage"),
    (re.compile(r"security", re.I), "security"),
    (re.compile(r"deck yacht|yacht.*module", re.I), "deck_yacht"),
    (re.compile(r"small vessel engineer|SV\b", re.I), "sv_engineering"),
    (re.compile(r"engine course|AEC|AEPC|general engineering", re.I), "engineering_other"),
    (re.compile(r"polar", re.I), "polar"),
    (re.compile(r"workboat", re.I), "workboat"),
]


@dataclass
class PdfLink:
    course_name: str
    url: str
    category: str


def download_mca_page(session: requests.Session) -> str:
    resp = session.get(MCA_ATP_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.text


def _infer_category(heading_text: str) -> str:
    for pattern, category in _HEADING_CATEGORY_MAP:
        if pattern.search(heading_text):
            return category
    return "other"


def fetch_pdf_links(html: str) -> list[PdfLink]:
    soup = BeautifulSoup(html, "lxml")
    links: list[PdfLink] = []
    current_category = "other"
    current_heading = ""

    for element in soup.find_all(["h2", "h3", "a"]):
        if element.name in ("h2", "h3"):
            current_heading = element.get_text(strip=True)
            current_category = _infer_category(current_heading)
        elif element.name == "a":
            href = element.get("href", "")
            if "assets.publishing.service.gov.uk" in href and href.endswith(".pdf"):
                course_name = element.get_text(strip=True)
                if not course_name:
                    course_name = current_heading
                links.append(PdfLink(
                    course_name=course_name,
                    url=href,
                    category=current_category,
                ))

    logger.info("Discovered %d PDF links from MCA ATP page", len(links))
    return links
