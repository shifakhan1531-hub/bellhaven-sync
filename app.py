import json
from flask import Flask, request, redirect, url_for, flash, render_template_string
import db
import writeback

app = Flask(__name__)
app.secret_key = "local-dev-only"

TEMPLATE = """
<!doctype html>
<title>Bellhaven review</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 980px; margin: 24px auto; padding: 0 12px; background: #f5f6f8; }
  .tabs a { margin-right: 14px; text-decoration: none; color: #345; font-weight: bold; }
  .tabs a.on { border-bottom: 3px solid #2563eb; }
  .card { background: white; border-radius: 8px; padding: 14px 16px; margin: 14px 0; box-shadow: 0 1px 3px #0002; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; color: white; font-size: 12px; font-weight: bold; }
  .REPARENT,.RENAME { background: #2563eb; } .CHOW,.CHOW_LINK { background: #c2410c; }
  .CREATE { background: #15803d; } .DUPLICATE { background: #7c3aed; }
  .ORPHAN,.REVIEW_INACTIVE { background: #64748b; }
  .ev { font-family: Consolas, monospace; font-size: 13px; background: #f1f5f9; padding: 4px 8px; margin: 3px 0; border-radius: 4px; }
  .call { font-family: Consolas, monospace; font-size: 12px; background: #fef9c3; padding: 4px 8px; margin: 3px 0; word-break: break-all; }
  button { padding: 7px 18px; border: 0; border-radius: 5px; color: white; font-weight: bold; cursor: pointer; margin-right: 8px; }
  .approve { background: #16a34a; } .reject { background: #dc2626; }
  .flash { background: #e0f2fe; padding: 10px; border-radius: 6px; margin: 8px 0; }
</style>
<h2>Bellhaven CRM review</h2>
<div class="tabs">
  {% for v in ['pending','approved','rejected'] %}
    <a href="/?view={{ v }}" class="{{ 'on' if v == view }}">{{ v.title() }} ({{ counts[v] }})</a>
  {% endfor %}
</div>
{% for m in get_flashed_messages() %}<div class="flash">{{ m }}</div>{% endfor %}
{% for r in rows %}
  <div class="card">
    <span class="badge {{ r.p.type }}">{{ r.p.type }}</span>
    <b>{{ r.p.account_name or r.p.website.name }}</b>
    &nbsp; confidence: {{ r.p.confidence }}
    <div style="margin-top:8px"><b>Evidence</b></div>
    {% for line in r.p.evidence %}<div class="ev">{{ line }}</div>{% endfor %}
    <div style="margin-top:8px"><b>If approved, this is sent to the CRM:</b></div>
    {% for c in r.calls %}<div class="call">{{ c }}</div>{% endfor %}
    {% if view == 'pending' %}
      <form method="post" action="/decide" style="margin-top:10px">
        <input type="hidden" name="key" value="{{ r.key }}">
        <input type="hidden" name="view" value="{{ view }}">
        <button class="approve" name="action" value="approve">Approve</button>
        <button class="reject" name="action" value="reject">Reject</button>
      </form>
      {% if r.result %}<div class="ev">Previous attempt: {{ r.result }}</div>{% endif %}
    {% else %}
      <div class="ev">Result: {{ r.result }} ({{ r.decided_at }})</div>
    {% endif %}
  </div>
{% else %}
  <p>Nothing here.</p>
{% endfor %}
"""


@app.route("/")
def index():
    view = request.args.get("view", "pending")
    rows = []
    for r in db.list_proposals(view):
        p = json.loads(r["payload"])
        rows.append({"key": r["key"], "p": p, "result": r["result"],
                     "decided_at": r["decided_at"], "calls": writeback.describe_calls(p)})
    counts = {s: len(db.list_proposals(s)) for s in ("pending", "approved", "rejected")}
    return render_template_string(TEMPLATE, rows=rows, view=view, counts=counts)


@app.route("/decide", methods=["POST"])
def decide():
    key = request.form["key"]
    action = request.form["action"]
    view = request.form.get("view", "pending")
    row = db.get_proposal(key)

    if row is None or row["status"] != "pending":
        flash("That proposal was already decided.")
    elif action == "reject":
        db.set_decision(key, "rejected", "rejected by reviewer")
        flash("Rejected. Nothing was written to the CRM.")
    elif action == "approve":
        p = json.loads(row["payload"])
        try:
            result = writeback.apply_proposal(
                p, row["result"] or "",
                on_progress=lambda text: db.set_decision(key, "pending", text))
            db.set_decision(key, "approved", result)
            flash("Approved and written to the CRM: " + result)
        except Exception as e:
            flash("FAILED, nothing marked as done: " + str(e))
    return redirect(url_for("index", view=view))


if __name__ == "__main__":
    app.run(debug=True)