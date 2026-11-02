import json
import bellhaven_scraper as scraper
import crm_client
import matcher
import db


def main():
    print("1/4 Scraping website...")
    links = scraper.get_all_links()
    locations = []
    for link in links:
        try:
            locations.append(scraper.parse_community(link))
        except Exception as e:
            print("   FAILED:", link, e)
    json.dump(locations, open("locations.json", "w", encoding="utf-8"), indent=2)
    print(f"   {len(locations)} locations")

    print("2/4 Downloading CRM accounts...")
    accounts = crm_client.get_all_accounts()
    json.dump(accounts, open("accounts.json", "w", encoding="utf-8"), indent=2)
    print(f"   {len(accounts)} accounts")

    print("3/4 Matching...")
    proposals, confident = matcher.run_matching(locations, accounts)
    print(f"   {len(confident)} confident matches, {len(proposals)} proposals")

    print("4/4 Saving proposals (skipping already-decided ones)...")
    added, refreshed, skipped = db.save_new_proposals(proposals)
    print(f"   new: {added}   still pending: {refreshed}   already decided (skipped): {skipped}")


if __name__ == "__main__":
    main()