from sop import decide_parent_change

assert decide_parent_change({"lifetime_revenue": 100000, "outstanding_ar": 9000}) == "CHOW"
assert decide_parent_change({"lifetime_revenue": 100000, "outstanding_ar": 0}) == "REPARENT"
assert decide_parent_change({"lifetime_revenue": 0, "outstanding_ar": 500}) == "REPARENT"
assert decide_parent_change({"lifetime_revenue": 0, "outstanding_ar": 0}) == "REPARENT"
assert decide_parent_change({}) == "REPARENT"
print("All billing rule tests passed")