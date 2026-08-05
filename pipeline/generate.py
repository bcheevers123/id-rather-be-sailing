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
from pipeline.adapters.south_shields import SouthShieldsAdapter
from pipeline.adapters.bluewater import BluewaterAdapter
from pipeline.adapters.pyt_za import PytZaAdapter
from pipeline.adapters.north_kent import NorthKentAdapter
from pipeline.adapters.nafc import NafcAdapter
from pipeline.adapters.yacht_crew_training import YachtCrewTrainingAdapter
from pipeline.adapters.mpt_usa import MptUsaAdapter
from pipeline.adapters.utt import UttAdapter
from pipeline.adapters.east_coast_college import EastCoastCollegeAdapter
from pipeline.adapters.pyt_usa import PytUsaAdapter
from pipeline.adapters.sailing_gi import SailingGiAdapter
from pipeline.adapters.sw_maritime import SwMaritimeAdapter
from pipeline.adapters.glasgow_college import GlasgowCollegeAdapter
from pipeline.adapters.himt import HimtAdapter
from pipeline.adapters.searegs import SearegsAdapter
from pipeline.adapters.bp_marine import BpMarineAdapter
from pipeline.adapters.galileo import GalileoAdapter
from pipeline.adapters.smaritime import SmaritimeAdapter
from pipeline.adapters.seamanship_ie import SeamanshipIeAdapter
from pipeline.adapters.fire_aid import FireAidAdapter
from pipeline.adapters.mitags import MitagsAdapter
from pipeline.adapters.uhi_nwh import UhiNwhAdapter
from pipeline.adapters.hss import HssAdapter
from pipeline.adapters.stream_marine import StreamMarineAdapter
from pipeline.adapters.you_and_sea import YouAndSeaAdapter
from pipeline.adapters.hitby_fishing import HitbyFishingAdapter
from pipeline.adapters.north_kent_college import NorthKentCollegeAdapter
from pipeline.adapters.idess import IdessAdapter
from pipeline.adapters.maritime_training_in import MaritimeTrainingInAdapter
from pipeline.adapters.city_of_glasgow import CityOfGlasgowAdapter
from pipeline.adapters.ondeck import OndeckAdapter
from pipeline.adapters.serco_marine import SercoMarineAdapter
from pipeline.adapters.lagan_marine import LaganMarineAdapter
from pipeline.adapters.medaire import MedAireAdapter
from pipeline.adapters.nmci import NmciAdapter
from pipeline.adapters.palma_sea import PalmaSeaAdapter
from pipeline.adapters.estern import EsternAdapter
from pipeline.adapters.hamble import HambleAdapter
from pipeline.adapters.ddrc import DDRCAdapter
from pipeline.adapters.ssm_hr import SsmHrAdapter
from pipeline.adapters.stc import StcAdapter
from pipeline.adapters.resolve_academy import ResolveAcademyAdapter
from pipeline.adapters.nma_sa import NmaSaAdapter
from pipeline.adapters.gibraltar_maritime import GibraltarMaritimeAdapter
from pipeline.adapters.ocean_tg import OceanTgAdapter
from pipeline.adapters.orkney_uhi import OrkneyUhiAdapter
from pipeline.adapters.rnli import RnliAdapter
from pipeline.adapters.defelice import DefeliceAdapter
from pipeline.adapters.hlscc import HlsccAdapter
from pipeline.adapters.ipowerboat import IpowerboatAdapter
from pipeline.adapters.cernetmrcc import CernetmrccAdapter
from pipeline.adapters.marine_radio import MarineRadioAdapter
from pipeline.adapters.evergreen_marine import EvergreenMarineAdapter
from pipeline.adapters.securewest import SecurewestAdapter
from pipeline.adapters.falmouth_marine_school import FalmouthMarineSchoolAdapter
from pipeline.adapters.lr import LrAdapter
from pipeline.adapters.cae import CaeAdapter
from pipeline.adapters.wavetrain import WavetrainAdapter
from pipeline.adapters.abb_marine import AbbMarineAdapter
from pipeline.adapters.faraday_centre import FaradayCentreAdapter
from pipeline.adapters.aset import AsetAdapter
from pipeline.adapters.seefunkschule import SeefunkschuleAdapter
from pipeline.adapters.namtc import NamtcAdapter
from pipeline.geocode import geocode_providers
from pipeline.change_detector import detect_changes
from pipeline.freshness import compute_freshness
from pipeline.mca_source import PdfLink, download_mca_page, fetch_pdf_links
from pipeline.normalise import make_slug, normalise_provider, canonical_name
from pipeline.pdf_parser import parse_pdf
from pipeline.report import build_coverage_report
from pipeline.validate import validate_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"

DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "public" / "data"

ARLO_ADAPTERS: dict[str, list[dict]] = {
    # Each entry uses "domain" to match all providers sharing that website.
    # The loop below iterates every provider whose website contains that domain.
    "pst": [
        {"subdomain": "maritimeskillsacademy", "course_path": "/courses/stcw-basic-safety-training", "domain": "maritimeskillsacademy.com"},
    ],
}

# You and Sea Ltd — calendar page is Squarespace JS-rendered; adapter returns []
# unless SSR event markup becomes available.
# All 10 approved courses share the same calendar URL; each has a distinct provider_id
# (you-and-sea-ltd through you-and-sea-ltd-10) per the MCA approvals data.
YOU_AND_SEA_COURSE_IDS: set[str] = {
    "pst", "efa", "pssr", "mfa", "mc", "upst", "helm-o", "ecdis",
    "workboat-nav-radar", "workboat-stability",
}
YOU_AND_SEA_CALENDAR_URL = "https://youandsea.com/course-calendar"

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
    canonical_to_provider_id: dict[str, str] = {}

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
                canon = canonical_name(raw.raw_name)
                if canon in canonical_to_provider_id:
                    # Same provider seen under a slightly different name — reuse existing ID
                    pid = canonical_to_provider_id[canon]
                    raw_name_to_provider_id[raw.raw_name] = pid
                    continue
                provider_dict = normalise_provider(
                    raw.raw_name, raw.location, raw.address,
                    raw.contact_details, raw.not_open_to_public, existing_slugs,
                )
                if not raw.is_uk:
                    provider_dict["country"] = None
                pid = provider_dict["id"]
                providers_by_id[pid] = provider_dict
                canonical_to_provider_id[canon] = pid
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
    raw_providers = list(providers_by_id.values())
    geocode_providers(raw_providers)
    valid_providers = validate_all("provider", raw_providers)
    valid_approvals = validate_all("approval", approvals)

    offerings: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    # Arlo adapter — loops all providers whose website matches the configured domain
    for course_id, adapter_configs in ARLO_ADAPTERS.items():
        for cfg in adapter_configs:
            adapter = ArloAdapter(cfg["subdomain"], cfg["course_path"], course_id)
            for pid, provider in providers_by_id.items():
                if cfg["domain"] in (provider.get("website") or ""):
                    raw_offerings = adapter.fetch(provider)
                    for o in raw_offerings:
                        o.freshness_status = compute_freshness(o.last_verified, now_iso)
                        offerings.append(o.to_dict())

    # UKSA adapter — loops all 14 uksa.org providers, one UKSAAdapter per course
    for course_id in UKSA_COURSE_URLS:
        uksa_adapter = UKSAAdapter(course_id)
        for pid, provider in providers_by_id.items():
            if "uksa.org" in (provider.get("website") or ""):
                raw_offerings = uksa_adapter.fetch(provider)
                for o in raw_offerings:
                    o.freshness_status = compute_freshness(o.last_verified, now_iso)
                    offerings.append(o.to_dict())

    # Stream Marine adapter — loops all streammarinetraining.com providers
    for course_id, source_url in STREAM_MARINE_ADAPTERS.items():
        stream_adapter = StreamMarineAdapter(course_id, source_url)
        for pid, provider in providers_by_id.items():
            if "streammarinetraining.com" in (provider.get("website") or ""):
                raw_offerings = stream_adapter.fetch(provider)
                for o in raw_offerings:
                    o.freshness_status = compute_freshness(o.last_verified, now_iso)
                    offerings.append(o.to_dict())

    # Solent / Warsash adapter — loops all 46 maritime.solent.ac.uk providers (API caches internally)
    solent_adapter = SolentAdapter()
    for pid, provider in providers_by_id.items():
        if "maritime.solent.ac.uk" in (provider.get("website") or ""):
            raw_offerings = solent_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Blackpool and The Fylde College adapter
    blackpool_adapter = BlackpoolAdapter()
    for pid, provider in providers_by_id.items():
        if "fleetwoodnautical.blackpool.ac.uk" in (provider.get("website") or ""):
            raw_offerings = blackpool_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # You and Sea — one fetch per course_id (the calendar covers all courses).
    # Multiple provider IDs share the same website; only call once per course.
    _you_and_sea_done: set[str] = set()
    you_and_sea_provider = next(
        (p for p in providers_by_id.values() if "youandsea.com" in (p.get("website") or "")),
        None,
    )
    if you_and_sea_provider:
        for course_id in YOU_AND_SEA_COURSE_IDS:
            if course_id in _you_and_sea_done:
                continue
            adapter = YouAndSeaAdapter(course_id, YOU_AND_SEA_CALENDAR_URL)
            raw_offerings = adapter.fetch(you_and_sea_provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())
            _you_and_sea_done.add(course_id)

    # Falmouth Training Solutions — after provider dedup all approvals share one provider ID.
    # Use domain lookup so it still works if the slug changes.
    falmouth_ts_provider = next(
        (p for p in providers_by_id.values() if "falmouthtrainingsolutions.co.uk" in (p.get("website") or "")),
        providers_by_id.get("falmouth-training-solutions"),
    )
    falmouth_ms_provider = next(
        (p for p in providers_by_id.values() if "falmouthmarineschool" in (p.get("website") or "")),
        providers_by_id.get("falmouth-marine-school"),
    )
    FALMOUTH_COURSE_PROVIDERS = {
        "pst": falmouth_ts_provider,
        "fpff": falmouth_ts_provider,
        "pssr": falmouth_ts_provider,
        "helm-o": falmouth_ts_provider,
        "security-awareness": falmouth_ts_provider,
        "dsd": falmouth_ts_provider,
        "aec1": falmouth_ts_provider,
        "aec2": falmouth_ms_provider,
        "workboat-nav-radar": falmouth_ts_provider,
        "workboat-stability": falmouth_ts_provider,
    }
    for course_id, provider in FALMOUTH_COURSE_PROVIDERS.items():
        if not provider:
            continue
        adapter = FalmouthAdapter(course_id)
        raw_offerings = adapter.fetch(provider)
        for o in raw_offerings:
            o.freshness_status = compute_freshness(o.last_verified, now_iso)
            offerings.append(o.to_dict())

    # Seahaven Maritime Academy (3 provider IDs all share one website)
    seahaven_adapter = SeahavenAdapter()
    for pid, provider in providers_by_id.items():
        if "seahavenmaritimeacademy.co.uk" in (provider.get("website") or ""):
            raw_offerings = seahaven_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # HOTA (Humberside Offshore Training Association — up to 9 provider IDs, all share one website)
    hota_adapter = HotaAdapter()
    for pid, provider in providers_by_id.items():
        if "hota.org" in (provider.get("website") or ""):
            raw_offerings = hota_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Petans (up to 5 provider IDs, all share one website)
    petans_adapter = PetansAdapter()
    for pid, provider in providers_by_id.items():
        if "petans.co.uk" in (provider.get("website") or ""):
            raw_offerings = petans_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Seascope Maritime Training (8 provider IDs, all share one website)
    seascope_adapter = SeascopeAdapter()
    for pid, provider in providers_by_id.items():
        if "seascopemaritimetraining.com" in (provider.get("website") or ""):
            raw_offerings = seascope_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Seafood Cornwall Training Ltd (8 provider IDs, all share one website)
    seafood_adapter = SeafoodCornwallAdapter()
    for pid, provider in providers_by_id.items():
        if "seafoodcornwalltraining.co.uk" in (provider.get("website") or ""):
            raw_offerings = seafood_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Flying Fish (Playwright — gracefully returns [] if Playwright not installed)
    # All 6 flying-fish-uk-ltd-* providers share the same website; loop them all.
    flying_fish_adapter = FlyingFishAdapter()
    for pid, provider in providers_by_id.items():
        if "flyingfishonline.com" in (provider.get("website") or ""):
            raw_offerings = flying_fish_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Chieftain Training (Playwright — 9 providers all share chieftain.training)
    chieftain_adapter = ChieftainAdapter()
    for pid, provider in providers_by_id.items():
        if "chieftain.training" in (provider.get("website") or ""):
            raw_offerings = chieftain_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # RelyOn Nutec (Playwright — scrapes all locations, emits provider_ids from site data)
    # Use a domain loop but only call fetch() once (adapter ignores the provider arg and
    # fetches the whole site); a sentinel flag prevents duplicate runs.
    _relyon_done = False
    relyon_adapter = RelyOnAdapter()
    for pid, provider in providers_by_id.items():
        if "relyonnutec.com" in (provider.get("website") or "") and not _relyon_done:
            raw_offerings = relyon_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())
            _relyon_done = True

    # STCW Training UK (Playwright) — loop all providers sharing stcw-training-uk.com
    stcw_uk_adapter = StcwTrainingUkAdapter()
    for pid, provider in providers_by_id.items():
        if "stcw-training-uk.com" in (provider.get("website") or ""):
            raw_offerings = stcw_uk_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # 3T Global (Playwright) — loop all 9 provider records sharing 3tglobal.com
    three_t_adapter = ThreeTAdapter()
    for pid, provider in providers_by_id.items():
        if "3tglobal.com" in (provider.get("website") or ""):
            raw_offerings = three_t_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # South Shields Marine School (EBSonTrack system, 22 providers sharing one booking system)
    south_shields_adapter = SouthShieldsAdapter()
    for pid, provider in providers_by_id.items():
        if "southshieldsmarineschool.com" in (provider.get("website") or ""):
            raw_offerings = south_shields_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Bluewater Yachting (38 providers across Spain/France/Italy)
    bluewater_adapter = BluewaterAdapter()
    for pid, provider in providers_by_id.items():
        if "bluewateryachting.com" in (provider.get("website") or ""):
            raw_offerings = bluewater_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # PYT South Africa (23 providers — all share one calendar)
    pyt_za_adapter = PytZaAdapter()
    for pid, provider in providers_by_id.items():
        if "pyt.co.za" in (provider.get("website") or ""):
            raw_offerings = pyt_za_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # North Kent College / NMTC Training (12 providers, real data on nmtctraining.co.uk)
    north_kent_adapter = NorthKentAdapter()
    for pid, provider in providers_by_id.items():
        if "northkent.ac.uk" in (provider.get("website") or ""):
            raw_offerings = north_kent_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # NAFC / Shetland UHI (11 providers)
    nafc_adapter = NafcAdapter()
    for pid, provider in providers_by_id.items():
        website = provider.get("website") or ""
        if "nafc.ac.uk" in website or "shetland.uhi.ac.uk" in website:
            raw_offerings = nafc_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Yacht Crew Training / Seascope Antibes (Shopify, 11 providers)
    yct_adapter = YachtCrewTrainingAdapter()
    for pid, provider in providers_by_id.items():
        if "yachtcrewtraining.com" in (provider.get("website") or ""):
            raw_offerings = yct_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Maritime Professional Training USA (MPT, 12 providers)
    mpt_usa_adapter = MptUsaAdapter()
    for pid, provider in providers_by_id.items():
        if "mptusa.com" in (provider.get("website") or ""):
            raw_offerings = mpt_usa_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # UTT Trinidad (12 providers)
    utt_adapter = UttAdapter()
    for pid, provider in providers_by_id.items():
        if "utt.edu.tt" in (provider.get("website") or ""):
            raw_offerings = utt_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # East Coast College / East Coast Training Academy (9 providers)
    east_coast_adapter = EastCoastCollegeAdapter()
    for pid, provider in providers_by_id.items():
        if "eastcoast.ac.uk" in (provider.get("website") or ""):
            raw_offerings = east_coast_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # PYT USA — Fort Lauderdale (11 providers, WordPress Events API)
    pyt_usa_adapter = PytUsaAdapter()
    for pid, provider in providers_by_id.items():
        if "professionalyachttraining.com" in (provider.get("website") or ""):
            raw_offerings = pyt_usa_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Allabroad Maritime Academy — Gibraltar (9 providers, WordPress static HTML)
    sailing_gi_adapter = SailingGiAdapter()
    for pid, provider in providers_by_id.items():
        if "sailing.gi" in (provider.get("website") or ""):
            raw_offerings = sailing_gi_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # South West Maritime Academy (8 providers, Arlo/WordPress)
    sw_maritime_adapter = SwMaritimeAdapter()
    for pid, provider in providers_by_id.items():
        if "southwestmaritimeacademy.com" in (provider.get("website") or ""):
            raw_offerings = sw_maritime_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # City of Glasgow College (10 providers, WooCommerce/FooEvents subdomain)
    glasgow_adapter = GlasgowCollegeAdapter()
    for pid, provider in providers_by_id.items():
        if "cityofglasgowcollege.ac.uk" in (provider.get("website") or ""):
            raw_offerings = glasgow_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # HIMT India (10 providers, static HTML on himtmarine.com)
    himt_adapter = HimtAdapter()
    for pid, provider in providers_by_id.items():
        if "himtoffshore.com" in (provider.get("website") or ""):
            raw_offerings = himt_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Searegs Training Ltd (7 providers, Arlo ipowerboat subdomain)
    searegs_adapter = SearegsAdapter()
    for pid, provider in providers_by_id.items():
        if "searegs" in (provider.get("website") or "").lower():
            raw_offerings = searegs_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # BP Marine Academy India (9 providers, ASP.NET WebForms booking system)
    bp_marine_adapter = BpMarineAdapter()
    for pid, provider in providers_by_id.items():
        if "bpmarine.in" in (provider.get("website") or ""):
            raw_offerings = bp_marine_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Galileo Maritime Academy Thailand (8 providers, WordPress AJAX)
    galileo_adapter = GalileoAdapter()
    for pid, provider in providers_by_id.items():
        if "galileomaritimeacademy.com" in (provider.get("website") or ""):
            raw_offerings = galileo_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Scottish Maritime Academy / NE Scotland College (6 providers, nescol.ac.uk)
    smaritime_adapter = SmaritimeAdapter()
    for pid, provider in providers_by_id.items():
        if "smaritime.co.uk" in (provider.get("website") or ""):
            raw_offerings = smaritime_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # The Seamanship Centre — Ireland (6 providers, Tribe Events REST API)
    seamanship_ie_adapter = SeamanshipIeAdapter()
    for pid, provider in providers_by_id.items():
        if "seamanship.ie" in (provider.get("website") or ""):
            raw_offerings = seamanship_ie_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Fire Aid Academy Hythe (7 providers, bespoke .NET booking system)
    fire_aid_adapter = FireAidAdapter()
    for pid, provider in providers_by_id.items():
        if "fireaid.com" in (provider.get("website") or ""):
            raw_offerings = fire_aid_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # MITAGS USA (5 providers, static HTML course pages)
    mitags_adapter = MitagsAdapter()
    for pid, provider in providers_by_id.items():
        if "mitags.org" in (provider.get("website") or ""):
            raw_offerings = mitags_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # UHI North West and Hebrides (5 providers, Eventbrite API)
    uhi_nwh_adapter = UhiNwhAdapter()
    for pid, provider in providers_by_id.items():
        if "nwh.uhi.ac.uk" in (provider.get("website") or ""):
            raw_offerings = uhi_nwh_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # HSS / John Percival Marine Associates (7 providers, static HTML)
    hss_adapter = HssAdapter()
    for pid, provider in providers_by_id.items():
        if "hss.ac.uk" in (provider.get("website") or ""):
            raw_offerings = hss_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    north_kent_college_adapter = NorthKentCollegeAdapter()
    for pid, provider in providers_by_id.items():
        if "northkent.ac.uk" in (provider.get("website") or ""):
            raw_offerings = north_kent_college_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    hitby_fishing_adapter = HitbyFishingAdapter()
    for pid, provider in providers_by_id.items():
        if "whitbyfishingschool.co.uk" in (provider.get("website") or "") or "54northmaritime.co.uk" in (provider.get("website") or ""):
            raw_offerings = hitby_fishing_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    idess_adapter = IdessAdapter()
    for pid, provider in providers_by_id.items():
        if "idess.com.ph" in (provider.get("website") or "") or "idessmaritime.weebly.com" in (provider.get("website") or ""):
            raw_offerings = idess_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    maritime_training_in_adapter = MaritimeTrainingInAdapter()
    for pid, provider in providers_by_id.items():
        if "maritimetraining.in" in (provider.get("website") or ""):
            raw_offerings = maritime_training_in_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    city_of_glasgow_adapter = CityOfGlasgowAdapter()
    for pid, provider in providers_by_id.items():
        if "cityofglasgowcollege.ac.uk" in (provider.get("website") or ""):
            raw_offerings = city_of_glasgow_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Ondeck — requires Chrome profile with real browsing history to pass reCAPTCHA Enterprise;
    # returns [] in headless CI but is wired so it auto-populates if run with ONDECK_CHROME_PROFILE set
    ondeck_adapter = OndeckAdapter()
    for pid, provider in providers_by_id.items():
        if "ondecksailing.com" in (provider.get("website") or ""):
            raw_offerings = ondeck_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Serco Marine — domain parked (Azure holding page); returns [] until site is live
    serco_marine_adapter = SercoMarineAdapter()
    for pid, provider in providers_by_id.items():
        if "sercomarine.com" in (provider.get("website") or ""):
            raw_offerings = serco_marine_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    lagan_marine_adapter = LaganMarineAdapter()
    for pid, provider in providers_by_id.items():
        if "laganmarine.co.uk" in (provider.get("website") or ""):
            raw_offerings = lagan_marine_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    medaire_adapter = MedAireAdapter()
    for pid, provider in providers_by_id.items():
        if "medaire.com" in (provider.get("website") or ""):
            raw_offerings = medaire_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    nmci_adapter = NmciAdapter()
    for pid, provider in providers_by_id.items():
        if "nmci.ie" in (provider.get("website") or ""):
            raw_offerings = nmci_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    palma_sea_adapter = PalmaSeaAdapter()
    for pid, provider in providers_by_id.items():
        if "palmaseaschool.com" in (provider.get("website") or ""):
            raw_offerings = palma_sea_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Western Maritime Training — WAF-blocked (sgcaptcha), returns []
    estern_adapter = EsternAdapter()
    for pid, provider in providers_by_id.items():
        if "westernmaritime" in (provider.get("website") or "").lower():
            raw_offerings = estern_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Hamble School of Yachting (pst/efa/mfa/mc, booking-form select + prose dates)
    hamble_adapter = HambleAdapter()
    for pid, provider in providers_by_id.items():
        if "hamble.co.uk" in (provider.get("website") or ""):
            raw_offerings = hamble_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # DDRC Healthcare Plymouth (mfa/mc/efa, Arlo sessions, crawl-delay 10s)
    ddrc_adapter = DDRCAdapter()
    for pid, provider in providers_by_id.items():
        if "ddrc.org" in (provider.get("website") or "") or "ddrc.co.uk" in (provider.get("website") or ""):
            raw_offerings = ddrc_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # SSM Split (Croatia) — WordPress my-calendar API; returns [] until schedule published
    ssm_hr_adapter = SsmHrAdapter()
    for pid, provider in providers_by_id.items():
        if "ssm.hr" in (provider.get("website") or ""):
            raw_offerings = ssm_hr_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # STC / South Tyneside College — marine brand redirects to South Shields, returns []
    stc_adapter = StcAdapter()
    for pid, provider in providers_by_id.items():
        if "stc.ac.uk" in (provider.get("website") or ""):
            raw_offerings = stc_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Resolve Maritime Academy (data-course JSON attributes, USD prices)
    resolve_academy_adapter = ResolveAcademyAdapter()
    for pid, provider in providers_by_id.items():
        if "resolveacademy.com" in (provider.get("website") or ""):
            raw_offerings = resolve_academy_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # NMA Saudi Arabia — no public schedule, returns []
    nma_sa_adapter = NmaSaAdapter()
    for pid, provider in providers_by_id.items():
        if "nma.edu.sa" in (provider.get("website") or ""):
            raw_offerings = nma_sa_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # University of Gibraltar / Gibraltar Maritime Academy (dates TBD on site)
    gibraltar_maritime_adapter = GibraltarMaritimeAdapter()
    for pid, provider in providers_by_id.items():
        if "unigib.edu.gi" in (provider.get("website") or ""):
            raw_offerings = gibraltar_maritime_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Ocean TG / One Ocean — redirects to oneocean.com (e-learning only), returns []
    ocean_tg_adapter = OceanTgAdapter()
    for pid, provider in providers_by_id.items():
        if "oceantg.com" in (provider.get("website") or ""):
            raw_offerings = ocean_tg_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Orkney College UHI — no public STCW schedule, returns []
    orkney_uhi_adapter = OrkneyUhiAdapter()
    for pid, provider in providers_by_id.items():
        if "orkney.uhi.ac.uk" in (provider.get("website") or ""):
            raw_offerings = orkney_uhi_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # RNLI — CDN/WAF blocks all automated access (403 on all paths), returns []
    rnli_adapter = RnliAdapter()
    for pid, provider in providers_by_id.items():
        if "rnli.org" in (provider.get("website") or ""):
            raw_offerings = rnli_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # De Felice Srl Italy — calendar "under construction", returns []
    defelice_adapter = DefeliceAdapter()
    for pid, provider in providers_by_id.items():
        if "defelice.yachts" in (provider.get("website") or ""):
            raw_offerings = defelice_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # HLSCC British Virgin Islands — no upcoming events published, returns []
    hlscc_adapter = HlsccAdapter()
    for pid, provider in providers_by_id.items():
        if "hlscc.org" in (provider.get("website") or "") or "hlscc.edu.vg" in (provider.get("website") or ""):
            raw_offerings = hlscc_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Falmouth Marine School — 403 on all programmatic requests, returns []
    falmouth_marine_school_adapter = FalmouthMarineSchoolAdapter()
    for pid, provider in providers_by_id.items():
        if "falmouthmarineschool.ac.uk" in (provider.get("website") or ""):
            raw_offerings = falmouth_marine_school_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Lloyd's Register EMEA — SSO course, no public pricing
    lr_adapter = LrAdapter()
    for pid, provider in providers_by_id.items():
        if "lr.org" in (provider.get("website") or ""):
            raw_offerings = lr_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # CAE — aviation/defence simulation, no open STCW schedule, returns []
    cae_adapter = CaeAdapter()
    for pid, provider in providers_by_id.items():
        if "cae.com" in (provider.get("website") or ""):
            raw_offerings = cae_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Wavetrain — SSO/DSD static HTML, enquiry-only booking
    wavetrain_adapter = WavetrainAdapter()
    for pid, provider in providers_by_id.items():
        if "wavetrain.co.uk" in (provider.get("website") or ""):
            raw_offerings = wavetrain_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # ABB Marine Academy — JS SPA behind enterprise CDN, returns []
    abb_marine_adapter = AbbMarineAdapter()
    for pid, provider in providers_by_id.items():
        if "abb.com" in (provider.get("website") or ""):
            raw_offerings = abb_marine_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Faraday Centre — electrical safety only, no radio/GMDSS, returns []
    faraday_centre_adapter = FaradayCentreAdapter()
    for pid, provider in providers_by_id.items():
        if "faradaycentre.co.uk" in (provider.get("website") or ""):
            raw_offerings = faraday_centre_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # ASET International — GOC/ROC pages, no dates currently published, returns []
    aset_adapter = AsetAdapter()
    for pid, provider in providers_by_id.items():
        if "aset.co.uk" in (provider.get("website") or ""):
            raw_offerings = aset_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Seefunkschule Austria — static HTML schedule, ROC/LRC courses (German month names)
    seefunkschule_adapter = SeefunkschuleAdapter()
    for pid, provider in providers_by_id.items():
        if "seefunkschule.at" in (provider.get("website") or ""):
            raw_offerings = seefunkschule_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # NAMTC China — JS-only SaaS site, CMA courses don't map to STCW IDs, returns []
    namtc_adapter = NamtcAdapter()
    for pid, provider in providers_by_id.items():
        if "namtc.com.cn" in (provider.get("website") or ""):
            raw_offerings = namtc_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Evergreen Marine Corp — container shipping company, no STCW training schedule, returns []
    evergreen_marine_adapter = EvergreenMarineAdapter()
    for pid, provider in providers_by_id.items():
        if "evergreen-marine.com" in (provider.get("website") or ""):
            raw_offerings = evergreen_marine_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Securewest — online self-paced only (no scheduled dates), returns []
    securewest_adapter = SecurewestAdapter()
    for pid, provider in providers_by_id.items():
        if "securewest.com" in (provider.get("website") or ""):
            raw_offerings = securewest_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # Marine Radio / RT Training — static HTML, GOC/LRC/ROC pages
    marine_radio_adapter = MarineRadioAdapter()
    for pid, provider in providers_by_id.items():
        if "marineradio.co.uk" in (provider.get("website") or ""):
            raw_offerings = marine_radio_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # CERNET MRCC Italy — GOC/ROC calendario page, 41 offerings
    cernetmrcc_adapter = CernetmrccAdapter()
    for pid, provider in providers_by_id.items():
        if "cernetmrcc.com" in (provider.get("website") or ""):
            raw_offerings = cernetmrcc_adapter.fetch(provider)
            for o in raw_offerings:
                o.freshness_status = compute_freshness(o.last_verified, now_iso)
                offerings.append(o.to_dict())

    # iPowerboat Ltd — ipowerboat.co.uk redirects to searegs.co.uk, but providers.json
    # records the original URL; the Arlo endpoint is shared with SearegsAdapter.
    ipowerboat_adapter = IpowerboatAdapter()
    for pid, provider in providers_by_id.items():
        if "ipowerboat.co.uk" in (provider.get("website") or ""):
            raw_offerings = ipowerboat_adapter.fetch(provider)
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

    import os
    gc_token = os.environ.get("GOATCOUNTER_TOKEN", "")
    if gc_token:
        try:
            gc_resp = session.get(
                "https://idratherbesailing.goatcounter.com/api/v0/stats/total",
                headers={"Authorization": f"Bearer {gc_token}"},
                timeout=10,
            )
            if gc_resp.ok:
                gc_data = gc_resp.json()
                _write_json(out_dir / "stats.json", {"total_visitors": gc_data.get("total", 0)})
                logger.info("GoatCounter total visitors: %d", gc_data.get("total", 0))
            else:
                logger.warning("GoatCounter API returned %d", gc_resp.status_code)
        except Exception as exc:
            logger.warning("GoatCounter fetch failed: %s", exc)
    else:
        logger.info("GOATCOUNTER_TOKEN not set — skipping stats.json")

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
