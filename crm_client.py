import json
import requests
from collections import Counter

import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["BELLHAVEN_TOKEN"]
BASE = "https://analyst-assessment-production.up.railway.app/api/v1"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
BELLHAVEN_PARENT_ID = "0015QAPLGS3FVYEEEM"


def get_all_accounts():
    """Download every account, page by page."""
    accounts = []
    page = 1
    while True:
        r = requests.get(
            f"{BASE}/accounts",
            headers=HEADERS,
            params={"page": page, "page_size": 50},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        accounts.extend(body["data"])
        if len(accounts) >= body["total"] or not body["data"]:
            break
        page += 1
    return accounts


if __name__ == "__main__":
    accounts = get_all_accounts()

    with open("accounts.json", "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2)

    print(f"Downloaded {len(accounts)} accounts -> accounts.json")

    print("\nAccounts per parent:")
    parents = Counter((a["parent_id"], a["parent_name"]) for a in accounts)
    for (pid, pname), count in parents.most_common():
        print(f"  {count:3d}  {pname or '(no parent)'}  [{pid or '-'}]")

    print("\nAccounts per status:")
    for status, count in Counter(a["status"] for a in accounts).items():
        print(f"  {count:3d}  {status}")

    at_risk = [
        a for a in accounts
        if a["lifetime_revenue"] > 0 and a["outstanding_ar"] > 0
    ]
    print(f"\nAccounts with revenue AND outstanding AR (billing rule applies): {len(at_risk)}")
    for a in at_risk:
        print(f"  {a['name']}  rev={a['lifetime_revenue']}  ar={a['outstanding_ar']}")