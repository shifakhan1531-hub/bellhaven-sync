# Bellhaven CRM Sync

Scrapes the Bellhaven website, matches every location to the CRM, and proposes
fixes that a human approves or rejects. Nothing writes to the CRM without approval.

## Run it
pip install -r requirements.txt
Create .env with BELLHAVEN_TOKEN=<your token>
python run_pipeline.py   # scrape, match, save new proposals
python app.py            # review app at http://127.0.0.1:5000
Schedule: .github/workflows/daily.yml runs the pipeline daily (proposals only).

## Matching approach
- Address first. Street names are normalized (Ln/Lane, Pk/Pike, NW/Northwest), then
  matched on street + zip, then street + city. Name similarity is only a last resort,
  because names change when facilities are rebranded.
- Each location becomes one of: confident match (15), REPARENT, RENAME, CREATE,
  DUPLICATE, ORPHAN, or a CHOW case.
- Duplicates: the survivor is the Bellhaven-owned account, or the one with billing
  history. The loser gets duplicate_of_account and Inactive.
- Billing SOP (sop.py, with tests): revenue > 0 AND outstanding AR > 0 means the old
  account is never re-parented. A new account is created under Bellhaven and
  chow_current_account is set on the old one. If the new owner's account already
  exists (Sandusky, sold to Millstone), only the link is set. The rule is re-checked
  against the live CRM at write time, so approving a bad REPARENT is blocked.
- Re-runs are safe: every proposal has a key (type + account + target) stored in SQLite.
  Decided proposals are skipped. Accounts already handed over via CHOW are ignored.

## Judgment calls
- The directory shows 34 communities, but the homepage lists a 35th (Findlay). The
  scraper also reads homepage links.
- Same-name lookalikes in other cities (Amberly Manor, New Carlisle vs Carlisle) are
  not matched, because the address differs.
- Union Square: the CRM has a similar account on a different street under a
  different owner. I rejected the CREATE as uncertain.

## How I used AI
I used Claude to explain the tools, draft the scraper, matcher, review app and
write-back, one file at a time. I checked the matcher against raw CRM data, which
caught abbreviation bugs (NW, Pk) and the Sandusky sold-facility case. I also ran
the pipeline twice to confirm re-runs don't repeat decisions.

## What I'd build next
- Fuzzy matching with a confidence score and an LLM tiebreaker for ambiguous cases
- Alerts (Slack or email) when new proposals appear
- Detecting parent changes from corporate sites or news
- An audit log and an undo step for approved changes

Time spent: [X] hours.