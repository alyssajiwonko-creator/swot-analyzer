"""
Headless UI smoke test using Streamlit's AppTest framework -- runs app.py in
a simulated session, types a ticker, clicks Analyze, and checks the script
completes without exceptions and renders the expected tabs/content. Network
calls are monkeypatched out with mock data since this sandbox can't reach
Yahoo Finance.
"""
import data_fetcher
from test_pipeline import healthy_company, risky_company

_mock = healthy_company()
data_fetcher.fetch_company_data = lambda ticker: _mock

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=30)
at.run()
assert not at.exception, f"Initial render raised: {at.exception}"
print("[OK] Initial render (no ticker analyzed yet) — no exceptions")

# Simulate typing a ticker and clicking Analyze
at.text_input[0].set_value("TEST")
at.button[0].click()
at.run()

if at.exception:
    for e in at.exception:
        print("EXCEPTION:", e)
    raise SystemExit("App raised an exception during analysis render")

print("[OK] Full analysis render — no exceptions")
print(f"Tabs rendered: {len(at.tabs)}")
print(f"Metrics rendered: {len(at.metric)}")
for m in at.metric:
    print(f"  - {m.label}: {m.value}")

# quick content sanity check across the whole app tree
full_text = " ".join([md.value for md in at.markdown] + [c.value for c in at.caption])
assert "Strengths" in full_text or any("Strengths" in b.label for b in at.button), "SWOT quadrant not found in render"
print("[OK] SWOT content found in render")
print("\nAll AppTest checks passed.")
