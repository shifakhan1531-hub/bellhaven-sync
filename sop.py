def decide_parent_change(account):
    """
    The billing SOP.
    Revenue history AND outstanding AR > 0  -> "CHOW"
        (don't touch the old account; create a new one, point the old one at it)
    Otherwise                               -> "REPARENT"
        (just change the parent on the existing account)
    """
    revenue = account.get("lifetime_revenue") or 0
    ar = account.get("outstanding_ar") or 0
    if revenue > 0 and ar > 0:
        return "CHOW"
    return "REPARENT"