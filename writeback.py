import json
import requests
from crm_client import BASE, HEADERS
from sop import decide_parent_change


def _check(r):
    if not r.ok:
        raise RuntimeError(f"CRM said {r.status_code}: {r.text[:400]}")
    return r.json() if r.text else {}


def _unwrap(resp):
    return resp.get("data", resp) if isinstance(resp, dict) else resp


def get_account(account_id):
    return _unwrap(_check(requests.get(f"{BASE}/accounts/{account_id}", headers=HEADERS, timeout=30)))


def patch_account(account_id, fields):
    return _check(requests.patch(f"{BASE}/accounts/{account_id}", headers=HEADERS, json=fields, timeout=30))


def create_account(fields):
    body = _unwrap(_check(requests.post(f"{BASE}/accounts", headers=HEADERS, json=fields, timeout=30)))
    return body.get("account_id") or body.get("id")


def describe_calls(p):
    """Plain-English list of the API calls an approval WOULD make (shown in the review app)."""
    k, ch, a = p["type"], p["changes"], p["account_id"]
    if k == "CREATE":
        return [f"POST /accounts  {json.dumps(ch['create_account'])}"]
    if k == "CHOW":
        return [f"POST /accounts  {json.dumps(ch['create_account'])}",
                f"PATCH /accounts/{a}  {{\"chow_current_account\": \"<new account id>\"}}   (nothing else on the old account changes)"]
    if k == "CHOW_LINK":
        return [f"PATCH /accounts/{a}  {json.dumps(ch)}"]
    return [f"PATCH /accounts/{a}  {json.dumps(ch)}"]


def apply_proposal(p, prior_result="", on_progress=None):
    """Send an approved proposal to the CRM. Only ever called from the Approve button."""
    kind, ch, acct = p["type"], p["changes"], p["account_id"]

    if kind == "CREATE":
        new_id = create_account(ch["create_account"])
        return f"created account {new_id}"

    if kind == "CHOW":
        old = get_account(acct)
        # Safety net: re-check the billing rule against the live CRM right now
        if decide_parent_change(old) != "CHOW":
            raise RuntimeError("Account no longer meets the CHOW condition. Re-run the pipeline.")
        if prior_result.startswith("created="):
            new_id = prior_result.split("=", 1)[1]          # a previous attempt already created it
        else:
            new_id = create_account(ch["create_account"])
            if on_progress:
                on_progress(f"created={new_id}")            # remember it so a retry can't create a second one
        patch_account(acct, {"chow_current_account": new_id})
        return f"created new account {new_id}; old account {acct} now points to it"

    if kind == "CHOW_LINK":
        patch_account(acct, {"chow_current_account": ch["chow_current_account"]})
        return f"linked {acct} -> {ch['chow_current_account']}"

    if kind == "REPARENT":
        live = get_account(acct)
        # Safety net: the billing SOP can never be bypassed
        if decide_parent_change(live) == "CHOW":
            raise RuntimeError("BLOCKED by billing SOP: this account has revenue AND outstanding AR. "
                               "It must not be re-parented.")
        patch_account(acct, {"parent_id": ch["parent_id"]})
        return f"re-parented {acct}"

    # RENAME, DUPLICATE, ORPHAN, REVIEW_INACTIVE are plain field updates
    patch_account(acct, ch)
    return f"updated {acct}: {json.dumps(ch)}"