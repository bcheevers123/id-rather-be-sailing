from dataclasses import dataclass


@dataclass
class Change:
    kind: str
    description: str
    severity: str  # "info" | "warning" | "critical"


def detect_changes(previous: dict, current: dict) -> list[Change]:
    changes: list[Change] = []

    prev_providers = {p["id"] for p in previous.get("providers", [])}
    curr_providers = {p["id"] for p in current.get("providers", [])}

    for pid in curr_providers - prev_providers:
        changes.append(Change("provider_added", f"New provider: {pid}", "info"))

    for pid in prev_providers - curr_providers:
        changes.append(Change("provider_removed", f"Provider removed: {pid}", "warning"))

    prev_offerings = previous.get("offerings_by_provider", {})
    curr_offerings = current.get("offerings_by_provider", {})

    for pid, prev_count in prev_offerings.items():
        curr_count = curr_offerings.get(pid, 0)
        if prev_count > 0 and curr_count == 0:
            changes.append(Change(
                "zero_offerings_anomaly",
                f"Provider {pid} had {prev_count} offerings, now has 0 — possible parser failure",
                "critical",
            ))

    return changes
