import json

accounts = json.load(open("accounts.json", encoding="utf-8"))
locations = json.load(open("locations.json", encoding="utf-8"))

keywords = ["chesterton", "batavia", "carlisle", "union", "amberly", "sandusky",
            "coldwater", "alliance", "monroe", "kettering", "owosso",
            "port clinton", "erie"]

for kw in keywords:
    print("\n=====", kw.upper(), "=====")
    for l in locations:
        if kw in l["name"].lower() or kw in l["city"].lower():
            print("  SITE:", l["name"], "|", l["address"], l["city"], l["state"], l["zip"])
    for a in accounts:
        if kw in a["name"].lower() or kw in (a["billing_city"] or "").lower():
            print("  CRM :", a["account_id"], "|", a["name"], "|", a["billing_street"],
                  a["billing_city"], a["billing_zip"], "|", a["parent_name"], "|", a["status"],
                  "| rev", a["lifetime_revenue"], "ar", a["outstanding_ar"],
                  "| dup_of:", a["duplicate_of_account"], "| chow:", a["chow_current_account"],
                  "| note:", a["note"])