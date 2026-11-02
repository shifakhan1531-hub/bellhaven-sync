import json
import re
from rapidfuzz import fuzz
from sop import decide_parent_change

BELLHAVEN_ID = "0015QAPLGS3FVYEEEM"

ABBREVIATIONS = {
    "st": "street", "ave": "avenue", "av": "avenue", "rd": "road",
    "dr": "drive", "ln": "lane", "blvd": "boulevard", "ct": "court",
    "hwy": "highway", "pkwy": "parkway", "pl": "place", "cir": "circle",
    "ter": "terrace", "trl": "trail", "pk": "pike",
    "nw": "northwest", "ne": "northeast", "sw": "southwest", "se": "southeast",
    "n": "north", "s": "south", "e": "east", "w": "west",
}


def norm_street(text):
    """'210 Orchard Ln.' and '210 orchard lane' become the same thing."""
    text = (text or "").lower()
    text = re.sub(r"\b(suite|ste|unit|apt)\b\.?\s*\w+", " ", text)
    text = re.sub(r"#\s*\w+", " ", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return " ".join(ABBREVIATIONS.get(w, w) for w in text.split())


def norm_name(text):
    """Lowercase, '&' to 'and', drop punctuation and the word 'the'."""
    text = (text or "").lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return " ".join(w for w in text.split() if w != "the")


def norm_city(text):
    return re.sub(r"[^a-z ]", "", (text or "").lower()).strip()


def zip5(text):
    return (text or "")[:5]


def describe_account(a):
    return (f"{a['name']} | {a['billing_street']}, {a['billing_city']} "
            f"{a['billing_state']} {a['billing_zip']} | parent: {a['parent_name'] or 'none'} "
            f"| status: {a['status']} | revenue ${a['lifetime_revenue']:,} | AR ${a['outstanding_ar']:,}")


def describe_location(loc):
    return f"{loc['name']} | {loc['address']}, {loc['city']} {loc['state']} {loc['zip']}"


def find_candidates(loc, accounts, by_addr, by_street_city):
    """Try the strongest signal first: address. Then weaker ones."""
    street = norm_street(loc["address"])

    found = by_addr.get((street, zip5(loc["zip"])))
    if found:
        return found, "exact address + zip"

    found = by_street_city.get((street, norm_city(loc["city"])))
    if found:
        return found, "street + city (zip differs)"

    # Last resort: similar name in the same city and state
    fuzzy = []
    for a in accounts:
        if norm_city(a["billing_city"]) == norm_city(loc["city"]) and a["billing_state"] == loc["state"]:
            score = fuzz.token_set_ratio(norm_name(a["name"]), norm_name(loc["name"]))
            if score >= 75:
                fuzzy.append(a)
    if fuzzy:
        return fuzzy, "name similarity + same city (address did NOT match)"
    return [], None


def make(kind, loc=None, account=None, target="", changes=None, evidence=None,
         method="", confidence="high"):
    acct_id = account["account_id"] if account else "new"
    return {
        "key": f"{kind}:{acct_id}:{target}",
        "type": kind,
        "account_id": account["account_id"] if account else None,
        "account_name": account["name"] if account else None,
        "website": loc,
        "changes": changes or {},
        "evidence": evidence or [],
        "matched_by": method,
        "confidence": confidence,
    }


def new_account_payload(loc):
    return {
        "name": loc["name"],
        "parent_id": BELLHAVEN_ID,
        "billing_street": loc["address"],
        "billing_city": loc["city"],
        "billing_state": loc["state"],
        "billing_zip": loc["zip"],
        "care_type": ", ".join(loc["care_offerings"]),
        "status": "Active",
    }


def run_matching(locations, accounts):
       # Accounts already handed over via CHOW are legacy records: never touch them again
    accounts = [a for a in accounts if not a.get("chow_current_account")]
    by_addr, by_street_city = {}, {}
    for a in accounts:
        by_addr.setdefault((norm_street(a["billing_street"]), zip5(a["billing_zip"])), []).append(a)
        by_street_city.setdefault((norm_street(a["billing_street"]), norm_city(a["billing_city"])), []).append(a)

    proposals, confident = [], []
    matched_ids = set()

    for loc in locations:
        cands, method = find_candidates(loc, accounts, by_addr, by_street_city)
        site_line = "WEBSITE: " + describe_location(loc)

        # 1. No CRM account at all
        if not cands:
            proposals.append(make(
                "CREATE", loc=loc, target=norm_name(loc["name"]),
                changes={"create_account": new_account_payload(loc)},
                evidence=[site_line, "CRM: no account found by address or similar name"],
                method="none"))
            continue

        for a in cands:
            matched_ids.add(a["account_id"])

        active = [a for a in cands if a["status"] == "Active" and not a.get("duplicate_of_account")]

        # 2. Only inactive matches: a human should decide
        if not active:
            a = cands[0]
            proposals.append(make(
                "REVIEW_INACTIVE", loc=loc, account=a, target="reactivate?",
                changes={"status": "Needs Review", "note": "On Bellhaven website but account is inactive"},
                evidence=[site_line, "CRM: " + describe_account(a)], method=method, confidence="low"))
            continue

        # 3. Several active matches = duplicates. Pick the best one to survive.
        active.sort(key=lambda a: (
            a["parent_id"] == BELLHAVEN_ID,
            a["lifetime_revenue"] > 0 or a["outstanding_ar"] > 0,
            a["billing_street"].strip().lower() == loc["address"].strip().lower(),
            bool(a["parent_id"]),
            a["lifetime_revenue"],
            a["outstanding_ar"]), reverse=True)
        survivor = active[0]
        losers = active[1:]

        for loser in losers:
            proposals.append(make(
                "DUPLICATE", loc=loc, account=loser, target=survivor["account_id"],
                changes={"duplicate_of_account": survivor["account_id"], "status": "Inactive"},
                evidence=[site_line, "KEEP:   " + describe_account(survivor),
                          "RETIRE: " + describe_account(loser)],
                method=method, confidence="medium"))

        # 4. Check the survivor for problems
        confidence = "high" if method.startswith(("exact", "street")) else "low"
        evidence = [site_line, "CRM:     " + describe_account(survivor), "Matched by: " + method]
        problem_found = False
        chow = False

        if survivor["parent_id"] != BELLHAVEN_ID:
            problem_found = True
            decision = decide_parent_change(survivor)
            if decision == "CHOW":
                chow = True
                proposals.append(make(
                    "CHOW", loc=loc, account=survivor, target=BELLHAVEN_ID,
                    changes={"create_account": new_account_payload(loc),
                             "set_chow_current_account_on_old": survivor["account_id"]},
                    evidence=evidence + [
                        f"BILLING RULE: revenue ${survivor['lifetime_revenue']:,} and AR ${survivor['outstanding_ar']:,} "
                        "-> old account stays UNCHANGED; create a new one under Bellhaven and link it via chow_current_account"],
                    method=method, confidence=confidence))
            else:
                proposals.append(make(
                    "REPARENT", loc=loc, account=survivor, target=BELLHAVEN_ID,
                    changes={"parent_id": BELLHAVEN_ID},
                    evidence=evidence + [
                        f"Current parent: {survivor['parent_name'] or 'none'} -> Bellhaven",
                        f"BILLING RULE: revenue ${survivor['lifetime_revenue']:,}, AR ${survivor['outstanding_ar']:,} "
                        "-> safe to re-parent directly"],
                    method=method, confidence=confidence))

        # Never rename an account we are leaving untouched for billing reasons
        if not chow and norm_name(survivor["name"]) != norm_name(loc["name"]):
            problem_found = True
            proposals.append(make(
                "RENAME", loc=loc, account=survivor, target=loc["name"],
                changes={"name": loc["name"]},
                evidence=evidence + [f"Name: '{survivor['name']}' -> '{loc['name']}'"],
                method=method, confidence=confidence))

        if not problem_found and not losers:
            confident.append({"website": loc, "account": survivor, "matched_by": method})

    # 5. Orphans: under Bellhaven in the CRM but not on the website
    for a in accounts:
        if (a["parent_id"] == BELLHAVEN_ID and a["status"] == "Active"
                and a["account_id"] not in matched_ids):

            # Same address under a different owner? Then it was probably sold.
            twins = [t for t in by_addr.get((norm_street(a["billing_street"]), zip5(a["billing_zip"])), [])
                     if t["account_id"] != a["account_id"]
                     and t["parent_id"] != BELLHAVEN_ID and t["status"] == "Active"]
            if twins:
                twin = twins[0]
                evidence = ["CRM (Bellhaven): " + describe_account(a),
                            "CRM (same address, other owner): " + describe_account(twin),
                            "WEBSITE: not listed -> likely sold to " + (twin["parent_name"] or "another owner")]
                if decide_parent_change(a) == "CHOW":
                    proposals.append(make(
                        "CHOW_LINK", account=a, target=twin["account_id"],
                        changes={"chow_current_account": twin["account_id"]},
                        evidence=evidence + [
                            "BILLING RULE: revenue and AR -> leave this account unchanged except "
                            "chow_current_account. New owner's account already exists, so no new account."],
                        method="same address under another parent", confidence="medium"))
                else:
                    proposals.append(make(
                        "DUPLICATE", account=a, target=twin["account_id"],
                        changes={"duplicate_of_account": twin["account_id"], "status": "Inactive"},
                        evidence=evidence + ["No billing history -> safe to retire as a duplicate"],
                        method="same address under another parent", confidence="medium"))
                continue

            proposals.append(make(
                "ORPHAN", account=a, target="needs-review",
                changes={"status": "Needs Review",
                         "note": "Not listed on Bellhaven website (checked automatically). Possibly sold or closed."},
                evidence=["CRM: " + describe_account(a), "WEBSITE: no matching community found"],
                method="none", confidence="medium"))

    return proposals, confident


if __name__ == "__main__":
    locations = json.load(open("locations.json", encoding="utf-8"))
    accounts = json.load(open("accounts.json", encoding="utf-8"))

    proposals, confident = run_matching(locations, accounts)

    json.dump(proposals, open("proposals.json", "w", encoding="utf-8"), indent=2)

    print(f"\nWebsite locations: {len(locations)}   CRM accounts: {len(accounts)}")
    print(f"Confident matches (nothing to fix): {len(confident)}")
    print(f"Proposals: {len(proposals)}\n")

    for kind in ["REPARENT", "CHOW", "CHOW_LINK", "RENAME", "CREATE", "DUPLICATE", "ORPHAN", "REVIEW_INACTIVE"]:
        group = [p for p in proposals if p["type"] == kind]
        print(f"=== {kind} ({len(group)}) ===")
        for p in group:
            site = p["website"]["name"] if p["website"] else "-"
            print(f"  [{p['confidence']}] CRM: {p['account_name'] or '(new)'}  <->  Website: {site}")
            print(f"        via {p['matched_by']}")
        print()