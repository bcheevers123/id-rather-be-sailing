"""Main pipeline orchestrator. Run as: python -m pipeline.generate"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from pipeline.adapters.arlo import ArloAdapter
from pipeline.adapters.blackpool import BlackpoolAdapter
from pipeline.adapters.chieftain import ChieftainAdapter
from pipeline.adapters.falmouth import FalmouthAdapter
from pipeline.adapters.flying_fish import FlyingFishAdapter
from pipeline.adapters.hota import HotaAdapter
from pipeline.adapters.petans import PetansAdapter
from pipeline.adapters.relyon import RelyOnAdapter
from pipeline.adapters.seafood_cornwall import SeafoodCornwallAdapter
from pipeline.adapters.seascope import SeascopeAdapter
from pipeline.adapters.seahaven import SeahavenAdapter
from pipeline.adapters.solent import SolentAdapter
from pipeline.adapters.stcw_training_uk import StcwTrainingUkAdapter
from pipeline.adapters.three_t import ThreeTAdapter
from pipeline.adapters.uksa import UKSAAdapter, COURSE_URLS as UKSA_COURSE_URLS
from pipeline.adapters.stream_marine import StreamMarineAdapter
from pipeline.adapters.you_and_sea import YouAndSeaAdapter
from pipeline.change_detector import detect_changes
from pipeline.freshness import compute_freshness
from pipeline.mca_source import PdfLink, download_mca_page, fetch_pdf_links
from pipeline.normalise import make_slug, normalise_provider
from pipeline.pdf_parser import parse_pdf
from pipeline.report import build_coverage_report
from pipeline.validate import validate_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"

DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "public" / "data"

ARLO_ADAPTERS: dict[str, list[dict]] = {
    "pst": [
        {"subdomain": "maritimeskillsacademy", "course_path": "/courses/stcw-basic-safety-training", "provider_id": "maritime-skills-academy-dover-part-of-viking-maritime-group"},
    ],
}

# You and Sea Ltd — calendar page is Squarespace JS-rendered; adapter returns []
# unless SSR event markup becomes available
YOU_AND_SEA_ADAPTERS: dict[str, str] = {
    "pst": "https://youandsea.com/course-calendar",
    "fpff": "https://youandsea.com/course-calendar",
    "efa": "https://youandsea.com/course-calendar",
    "pssr": "https://youandsea.com/course-calendar",
}

# Stream Marine uses Arlo-hosted event pages for each course
STREAM_MARINE_ADAPTERS: dict[str, str] = {
    "fpff": "https://streammarinetraining.com/arlo/events/5-stcw-fire-prevention-and-fire-fighting-fpff/",
    "efa": "https://streammarinetraining.com/arlo/events/8-stcw-elementary-first-aid-efa/",
    "pssr": "https://streammarinetraining.com/arlo/events/305-stcw-personal-safety-and-social-responsibility-stcw-security-awareness-pssrsa/",
    # PST is not offered separately by Stream Marine; it is bundled in the BSW (Basic Safety Training Week)
    "bsw": "https://streammarinetraining.com/arlo/events/61-stcw-basic-safety-training-week-bsw/",
    "stcw_refresher_5": "https://streammarinetraining.com/arlo/events/263-stcw-refresher-course-5-course-route-1-pstu-fpffu-pscrbu-affu-frbu/",
}

COURSE_NAME_TO_SLUG: dict[str, str] = {
    "Personal Survival Techniques": "pst",
    "Fire Prevention and Fire Fighting": "fpff",
    "Elementary First Aid": "efa",
    "Personal Safety and Social Responsibility": "pssr",
    "Advanced Fire Fighting": "aff",
    "Proficiency in Survival Craft and Rescue Boats": "pscrb",
    "Yacht-Restricted Proficiency in Survival Craft and Rescue Boats": "pscrb-r",
    "Proficiency in Medical First Aid": "mfa",
    "Proficiency in Medical Care": "mc",
    "Fast Rescue Boat": "frb",
    "Updating Fire Prevention and Fire Fighting": "ufpff",
    "Updating Advanced Fire Fighting": "uaff",
    "Updating Personal Survival Techniques": "upst",
    "Updating Proficiency in Survival Craft and Rescue Boats": "upscrb",
    "Updating Yacht-Restricted Proficiency in Survival Craft and Rescue Boats": "upscrb-r",
    "Updated Proficiency in Medical Care": "umc",
    "Updating Fast Rescue Boats": "ufrb",
    "Basic Oil and Chemical Tanker Training": "basic-oil-chem-tanker",
    "Basic Gas Tanker Training": "basic-gas-tanker",
    "MCA/MNTB Tanker Fire Fighting": "tanker-fire-fighting",
    "Advanced Oil Tanker Training": "advanced-oil-tanker",
    "Advanced Chemical Tanker Training": "advanced-chem-tanker",
    "Advanced Gas Tanker Training": "advanced-gas-tanker",
    "Basic Training for Ships Subject to the IGF Code": "basic-igf",
    "Advanced Training for Ships Subject to the IGF Code": "advanced-igf",
    "Fuel Specific Training for Service On Ships Covered by the IGF Code Using Gaseous or Liquid Hydrogen as a Fuel": "igf-hydrogen",
    "Basic Training for Ships Subject to the IGF Code - Ammonia": "igf-ammonia-basic",
    "Advanced Training for Ships Subject to the IGF Code - Ammonia": "igf-ammonia-advanced",
    "Basic Training for Ships Subject to the IGF Code - Methanol": "igf-methanol-basic",
    "Advanced Training for Ships Subject to the IGF Code - Methanol": "igf-methanol-advanced",
    "HELM Operational (O)": "helm-o",
    "HELM Management (M)": "helm-m",
    "ECDIS": "ecdis",
    "NAEST Operational (O)": "naest-o",
    "NAEST Management (M)": "naest-m",
    "General Operators Certificate (GOC)": "goc",
    "Restricted Operators Certificate (ROC)": "roc",
    "Long Range Certificate (LRC)": "lrc",
    "High Voltage Operational (O)": "hv-operational",
    "High Voltage Management (M)": "hv-management",
    "Security Awareness": "security-awareness",
    "Designated Security Duties": "dsd",
    "Ship Security Officer": "sso",
    "Company Security Officer": "cso",
    "Yacht Officer of Watch (OOW) General Ship Knowledge": "yacht-oow-gsk",
    "Yacht Officer of Watch (OOW) Navigation and Radar": "yacht-oow-nav-rad",
    "Yacht (Master) Business and Law": "yacht-master-business-law",
    "Yacht (Master) Navigation and Radar": "yacht-master-nav-rad",
    "Yacht (Master) Seamanship and Meteorology": "yacht-master-seamanship",
    "Yacht (Master) Ships Stability": "yacht-master-stability",
    "SV Initial Workshop Skills Training": "sv-workshop-skills",
    "SV Auxiliary Equipment Part - 1": "sv-aux-1",
    "SV Marine Diesel Engineering": "sv-marine-diesel",
    "SV Operational Procedures, Basic Hotel Services & Ship Construction": "sv-operational-procedures",
    "SV Chief Engineer Statutory & Operational Requirements": "sv-chief-engineer",
    "SV Applied Marine Engineering": "sv-applied-engineering",
    "SV Auxiliary Equipment Part - 2": "sv-aux-2",
    "General Engineering Science I & II": "ges-1-2",
    "Approved Engine Course part 1 (AEC1)": "aec1",
    "Approved Engine Course part 2 (AEC2)": "aec2",
    "Approved Electric Propulsion Course (AEPC) 1": "aepc-1",
    "Basic Training for Ships Operating in Polar Waters": "basic-polar",
    "Advanced Training for Ships Operating in Polar Waters": "advanced-polar",
    "Non-STCW Small Ships Navigation & Radar Training (under WBC3 syllabus)": "workboat-nav-radar",
    "Non-STCW One Day Stability Course (under WBC3 syllabus)": "workboat-stability",
    "Generic MASS Remote Operator Training Course (under MGN 703)": "mass-remote-operator",
    "Efficient Deck Hand": "edh",
    "Yacht Rating Certificate": "yrc",
    "Large Yacht Helideck Safety Training": "helideck",
    "Crisis Management & Human Behaviour": "cmhb",
    "Passenger Safety, Cargo Safety & Hull Integrity": "passenger-safety",
    "Shipboard Safety Officer": "shipboard-safety-officer",
    "Navigational Watch Rating Certificate - Special Training Route": "nwr-special",
    "Able Seafarer Deck CoP - Special Training Route": "ab-special",
}

COURSE_DESCRIPTIONS: dict[str, str] = {
    "pst": "Covers survival at sea: lifejackets, immersion suits, life rafts, and firefighting basics. Required for most commercial certificates.",
    "fpff": "Fire prevention and firefighting techniques. Covers fire theory, shipboard fire systems, and practical drills. Part of STCW Basic Safety Training.",
    "efa": "Provides basic first aid skills for use at sea before medical help arrives. Covers CPR, burns, and casualty care.",
    "pssr": "Covers personal safety procedures, onboard communication, and social responsibilities. Part of STCW Basic Safety Training.",
    "aff": "Advanced training in shipboard firefighting for designated firefighting team members.",
    "pscrb": "Advanced training in launching and operating survival craft and rescue boats.",
    "pscrb-r": "Yacht-specific variant of PSCRB, covering the survival craft found on smaller commercial yachts.",
    "frb": "Training in operation and recovery of fast rescue boats, typically required for vessels carrying fast rescue boats.",
    "helm-o": "Human Element, Leadership and Management — Officer of the Watch level. Covers communication, teamwork, and situational awareness.",
    "helm-m": "Human Element, Leadership and Management — Chief Officer / Master level. Builds on HELM-O with leadership and management responsibilities.",
    "ecdis": "Training in Electronic Chart Display and Information Systems, required for navigating on vessels equipped with ECDIS.",
    "goc": "General Operator Certificate for GMDSS (Global Maritime Distress and Safety System) radio communications.",
    "security-awareness": "Basic security awareness training covering the ISPS Code, threat recognition, and reporting procedures.",
    "sso": "Ship Security Officer training covering security plans, drills, and coordination with port and company security.",
    "edh": "Efficient Deck Hand — entry-level deck rating qualification covering watchkeeping, maintenance, and safety.",
}

CONFUSION_NOTES: dict[str, str] = {
    "pst": "This is the initial PST course. If you need to renew an existing certificate, see Updating PST (UPST).",
    "upst": "This is the refresher/updating course. For the initial certificate, see Personal Survival Techniques (PST).",
    "pscrb": "This is the full (unrestricted) PSCRB. For the yacht-specific variant, see Yacht-Restricted PSCRB (PSCRB-R).",
    "pscrb-r": "This is the yacht-restricted variant. For the full version, see Proficiency in Survival Craft and Rescue Boats (PSCRB).",
    "helm-o": "HELM Operational is for officer of the watch level. For chief officer / master level, see HELM Management (HELM-M).",
    "helm-m": "HELM Management is for chief officer / master level. For OOW level, see HELM Operational (HELM-O).",
    "basic-igf": "Basic IGF Training is the entry-level qualification. For the senior officer qualification, see Advanced IGF Training.",
    "advanced-igf": "Advanced IGF Training is the senior officer qualification. For entry-level, see Basic IGF Training.",
    "basic-oil-chem-tanker": "This is the basic (entry-level) oil and chemical tanker course. For the advanced qualification, see Advanced Oil Tanker Training.",
    "advanced-oil-tanker": "This is the advanced tanker training. For the entry-level course, see Basic Oil and Chemical Tanker Training.",
}


def download_pdf(url: str, session: requests.Session, dest_dir: Path) -> Path | None:
    filename = url.split("/")[-1]
    dest = dest_dir / filename
    if dest.exists():
        return dest
    try:
        time.sleep(2)
        resp = session.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        logger.info("Downloaded %s", filename)
        return dest
    except Exception as e:
        logger.error("Failed to download %s: %s", url, e)
        return None


def run_pipeline(dry_run: bool = False, output_dir: Path | None = None) -> None:
    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    logger.info("Fetching MCA ATP page…")
    try:
        html = download_mca_page(session)
    except Exception as e:
        logger.critical("Cannot fetch MCA page: %s — aborting", e)
        sys.exit(1)

    pdf_links = fetch_pdf_links(html)
    logger.info("Found %d PDF links", len(pdf_links))

    courses: list[dict] = []
    providers_by_id: dict[str, dict] = {}
    approvals: list[dict] = []
    parse_failures: list[dict] = []
    existing_slugs: set[str] = set()
    raw_name_to_provider_id: dict[str, str] = {}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for link in pdf_links:
            course_id = COURSE_NAME_TO_SLUG.get(link.course_name, make_slug(link.course_name))
            source_updated_date = _date_from_filename(link.url)

            pdf_path = download_pdf(link.url, session, tmp_path)
            if pdf_path is None:
                parse_failures.append({"provider_id": course_id, "reason": "PDF download failed"})
                continue

            try:
                parsed = parse_pdf(pdf_path, course_id, link.url, source_updated_date)
            except Exception as e:
                parse_failures.append({"provider_id": course_id, "reason": str(e)})
                logger.error("Parse error for %s: %s", course_id, e)
                continue

            time.sleep(2)

            for raw in parsed.providers:
                provider_dict = normalise_provider(
                    raw.raw_name, raw.location, raw.address,
                    raw.contact_details, raw.not_open_to_public, existing_slugs,
                )
                if not raw.is_uk:
                    provider_dict["country"] = None
                pid = provider_dict["id"]
                if pid not in providers_by_id:
                    providers_by_id[pid] = provider_dict
                raw_name_to_provider_id[raw.raw_name] = pid

            for raw_approval in parsed.approvals:
                pid = raw_name_to_provider_id.get(raw_approval.raw_provider_name) or make_slug(raw_approval.raw_provider_name)
                approvals.append({
                    "course_id": raw_approval.course_id,
                    "provider_id": pid,
                    "source_pdf_url": raw_approval.source_pdf_url,
                    "source_updated_date": raw_approval.source_updated_date,
                    "status": "active",
                    "first_seen": date.today().isoformat(),
                    "last_seen": date.today().isoformat(),
                    "not_open_to_public": raw_approval.not_open_to_public,
                })

            courses.append({
                "id": course_id,
                "official_name": link.course_name,
                "abbreviation": None,
                "aliases": [],
                "category": link.category,
                "description": COURSE_DESCRIPTIONS.get(course_id),
                "confusion_note": CONFUSION_NOTES.get(course_id),
                "source_pdf_url": link.url,
                "source_updated_date": source_updated_date,
                "provider_count": len(parsed.providers),
                "earliest_known_date": None,
                "lowest_known_price_gbp": None,
            })

    # Deduplicate approvals by (course_id, provider_id) - keep first seen
    seen_approval_keys: set[tuple[str, str]] = set()
    deduped_approvals: list[dict] = []
    for a in approvals:
        key = (a["course_id"], a["provider_id"])
        if key not in seen_approval_keys:
            seen_approval_keys.add(key)
            deduped_approvals.append(a)
    approvals = deduped_approvals

    valid_courses = validate_all("course", courses)
    valid_providers = validate_all("provider", list(providers_by_id.values()))
    valid_approvals = validate_all("approval", approvals)

    offerings: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for course_id, adapter_configs in ARLO_ADAPTERS.items():
        for cfg in adapter_configs:
            provider = providers_by_id.get(cfg["provider_id"])
            if not provider:
                continue
            adapter = ArloAdapter(cfg["subdomain"], cfg["course_path"], course_id)
            raw_offerings = adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # UKSA adapter
    for course_id in UKSA_COURSE_URLS:
        provider = providers_by_id.get("united-kingdom-sailing-academy-uksa")
        if not provider:
            logger.warning("UKSA provider not found in providers_by_id")
            continue
        adapter = UKSAAdapter(course_id)
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Stream Marine adapter
    for course_id, source_url in STREAM_MARINE_ADAPTERS.items():
        provider = providers_by_id.get("stream-marine-training")
        if not provider:
            logger.warning("Stream Marine provider not found in providers_by_id")
            continue
        adapter = StreamMarineAdapter(course_id, source_url)
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Solent / Warsash adapter
    solent_provider = providers_by_id.get("warsash-maritime-school-solent-university-southampton")
    if not solent_provider:
        logger.warning("Solent provider not found in providers_by_id")
    else:
        adapter = SolentAdapter()
        raw_offerings = adapter.fetch(solent_provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Blackpool and The Fylde College adapter
    blackpool_provider = providers_by_id.get("blackpool-and-the-fylde-college")
    if not blackpool_provider:
        logger.warning("Blackpool provider not found in providers_by_id")
    else:
        adapter = BlackpoolAdapter()
        raw_offerings = adapter.fetch(blackpool_provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # You and Sea adapter
    for course_id, source_url in YOU_AND_SEA_ADAPTERS.items():
        provider = providers_by_id.get("you-and-sea-ltd")
        if not provider:
            logger.warning("You and Sea provider not found in providers_by_id")
            continue
        adapter = YouAndSeaAdapter(course_id, source_url)
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Falmouth Training Solutions
    for course_id in ("pst", "fpff", "efa", "pssr"):
        provider = providers_by_id.get("falmouth-training-solutions")
        if not provider:
            logger.warning("Falmouth provider not found")
            break
        adapter = FalmouthAdapter(course_id)
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Seahaven Maritime Academy
    provider = providers_by_id.get("seahaven-maritime-academy")
    if not provider:
        logger.warning("Seahaven provider not found")
    else:
        adapter = SeahavenAdapter()
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # HOTA
    provider = providers_by_id.get("humberside-offshore-training-association-ltd")
    if not provider:
        logger.warning("HOTA provider not found")
    else:
        adapter = HotaAdapter()
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Petans
    provider = providers_by_id.get("petans-limited")
    if not provider:
        logger.warning("Petans provider not found")
    else:
        adapter = PetansAdapter()
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Seascope Maritime Training
    provider = providers_by_id.get("seascope-maritime-training")
    if not provider:
        logger.warning("Seascope provider not found")
    else:
        adapter = SeascopeAdapter()
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Seafood Cornwall
    provider = providers_by_id.get("seafood-cornwall-training-ltd")
    if not provider:
        logger.warning("Seafood Cornwall provider not found")
    else:
        adapter = SeafoodCornwallAdapter()
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Flying Fish (Playwright — gracefully returns [] if Playwright not installed)
    provider = providers_by_id.get("flying-fish-uk-ltd")
    if not provider:
        logger.warning("Flying Fish provider not found")
    else:
        adapter = FlyingFishAdapter()
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Chieftain Training (Playwright)
    provider = providers_by_id.get("chieftain-training")
    if not provider:
        logger.warning("Chieftain provider not found")
    else:
        adapter = ChieftainAdapter()
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # RelyOn Nutec (Playwright — emits offerings for multiple provider_ids)
    provider = providers_by_id.get("relyon-nutec-aberdeen")
    if not provider:
        logger.warning("RelyOn provider not found")
    else:
        adapter = RelyOnAdapter()
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # STCW Training UK (Playwright)
    provider = providers_by_id.get("stcw-training-uk-ltd")
    if not provider:
        logger.warning("STCW Training UK provider not found")
    else:
        adapter = StcwTrainingUkAdapter()
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # 3T Global (Playwright)
    provider = providers_by_id.get("3t-training-services-limited")
    if not provider:
        logger.warning("3T provider not found")
    else:
        adapter = ThreeTAdapter()
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    valid_offerings = validate_all("offering", offerings)

    # Back-fill earliest_known_date and lowest_known_price_gbp into courses from live offerings
    today_str = date.today().isoformat()
    from collections import defaultdict
    future_by_course: dict[str, list[dict]] = defaultdict(list)
    for o in valid_offerings:
        if o.get("start_date", "") >= today_str:
            future_by_course[o["course_id"]].append(o)
    for course in valid_courses:
        cid = course["id"]
        future = future_by_course.get(cid, [])
        if future:
            course["earliest_known_date"] = min(o["start_date"] for o in future)
            gbp_prices = [o["price"] for o in future if o.get("currency") == "GBP" and o.get("price") is not None]
            course["lowest_known_price_gbp"] = min(gbp_prices) if gbp_prices else None
        else:
            course["earliest_known_date"] = None
            course["lowest_known_price_gbp"] = None

    report = build_coverage_report(valid_courses, valid_providers, valid_approvals, valid_offerings, parse_failures)

    _write_json(out_dir / "courses.json", valid_courses)
    _write_json(out_dir / "providers.json", valid_providers)
    _write_json(out_dir / "approvals.json", valid_approvals)
    _write_json(out_dir / "offerings.json", valid_offerings)
    _write_json(out_dir / "coverage_report.json", report)
    _write_json(out_dir / "retrieval_log.json", [])

    logger.info(
        "Pipeline complete. %d courses, %d providers, %d approvals, %d offerings",
        len(valid_courses), len(valid_providers), len(valid_approvals), len(valid_offerings),
    )


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote %s", path.name)


def _date_from_filename(url: str) -> str:
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", url)
    if m:
        day, month, year = m.groups()
        return f"{year}-{month}-{day}"
    return date.today().isoformat()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run_pipeline(dry_run=args.dry_run)
