# Bellhaven CRM Sync

A small tool that keeps our CRM matched to the Bellhaven website. It finds
problems, suggests fixes, and only changes the CRM after a person approves.

## How to run it
1. `pip install -r requirements.txt`
2. Create a file called `.env` with: BELLHAVEN_TOKEN=your_token
3. `python run_pipeline.py` finds problems and saves proposals
4. `python app.py` opens the review page at http://127.0.0.1:5000

A daily schedule is set up in `.github/workflows/daily.yml`. It only finds
proposals. It never writes to the CRM.

## How matching works
I treated this like a CRM data-hygiene job. A facility's address rarely changes,
but its name often does, so I match on **address first** and name last.

- 35 locations on the website vs 121 CRM accounts
- 15 were already correct
- The rest became proposals: wrong parent, old name, duplicate, missing from the
  CRM, or in the CRM but no longer on the website

## The billing rule
If an account has revenue AND unpaid AR, I never change its parent. I create a
new account under Bellhaven and add a pointer on the old one. If either is zero,
I just change the parent. This rule has its own file and tests, and the app
re-checks it before every write.

## Safe to re-run
Every proposal has a unique key saved in a small database. Running the tool
again skips anything already approved or rejected.

## Things I checked myself
- The website directory shows 34 communities, but the homepage shows 35. I
  made sure the scraper picks up the missing one (Findlay).
- Same-name places in different towns (Carlisle, PA vs New Carlisle, OH) are
  not treated as matches.
- Sandusky is not on the website, but Millstone has an account at the same
  address. I treated it as sold and only linked it.
- I rejected Union Square because the CRM account has a different street and
  a different owner, so I could not be sure it was the same place.

## How I used AI
I used Claude as a guide because I am new to Python and APIs. It wrote the code
one file at a time and explained it. My part was checking the results against the
raw CRM data. That is how we caught address abbreviations like "NW" and "Pk"
and the Sandusky sold case.

## What I would do next
- Send an email or Slack alert when new proposals appear
- Add a confidence score so the most certain proposals are reviewed first
- Keep a log of every change so it can be undone

Time spent: [4] hours.