import requests
from crm_client import BASE, HEADERS, get_all_accounts

accounts = get_all_accounts()
names = {a["account_id"]: a["name"] for a in accounts}

print("Bellhaven accounts now:\n")
for a in accounts:
    if a["parent_id"] == "0015QAPLGS3FVYEEEM" or a["chow_current_account"] or a["duplicate_of_account"]:
        print(f"{a['name'][:42]:42} | {a['status']:12} | rev {a['lifetime_revenue']:>7} ar {a['outstanding_ar']:>6}"
              f" | dup_of: {names.get(a['duplicate_of_account'], '-')[:24]:24}"
              f" | chow -> {names.get(a['chow_current_account'], '-')[:24]}")