from datetime import datetime, timezone


def compute_freshness(last_verified_iso: str | None, now_iso: str) -> str:
    if not last_verified_iso:
        return "stale"
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    last = datetime.fromisoformat(last_verified_iso.replace("Z", "+00:00"))
    delta = now - last
    hours = delta.total_seconds() / 3600
    if hours < 24:
        return "verified"
    if hours < 24 * 7:
        return "recently_checked"
    return "stale"
