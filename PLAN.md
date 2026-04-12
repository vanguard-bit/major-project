# 🔬 Your Job: Collect Real Evaluation Results for the AIT Paper
**Role:** Run the prototype, gather numbers, fill the paper's evaluation section  
**What the paper needs from you:** A results table with real test cases, risk scores, detected violations, and precision metrics

---

## ⚠️ Important: Ethical & Legal Boundaries (Read First)

Before anything else, understand what you can and cannot do:

| ✅ Allowed | ❌ NOT Allowed |
|---|---|
| Testing apps you own / created | Testing production apps without authorization |
| Using officially published OAuth scopes from docs | Exploiting undisclosed vulnerabilities |
| Creating your own mock SaaS environment | Attacking real user data |
| Using public sandboxes / developer test accounts | Violating any platform's ToS |
| Documenting known, publicly disclosed over-permissioning patterns | Unauthorized API access |

**Bottom line:** You are *auditing behavior* using your own test accounts and developer sandboxes — not hacking. This is standard security research methodology (same as how RESTler, OWASP ZAP, and Burp Suite are used).

---

## 🗺️ Big Picture: What You're Doing

```
Your Prototype (AIT)
       │
       ▼
  Connects to a real or realistic OAuth-protected API
       │
       ▼
  Declares a limited scope (e.g., "read only")
       │
       ▼
  AIT sends adversarial/mutated API requests
       │
       ▼
  Checks: Did the API return data BEYOND what the scope should allow?
       │
       ▼
  Records: risk score, finding type, severity
       │
       ▼
  That becomes one row in your results table
```

You need **5–10 such rows** from **3–5 different integrations/platforms**.

---

## Phase 1 — Set Up Your Testing Environment

### Step 1: Get Your Prototype Running Locally

1. Clone/pull your team's latest code onto your machine
2. Install dependencies (Python + FastAPI assumed):
   ```bash
   pip install -r requirements.txt
   ```
3. Confirm the three microservices start correctly:
   - Audit Engine
   - Differential Fuzzer
   - Taint Tracker
4. Run the existing toy test to confirm output:
   ```bash
   python run_audit.py --config test_cases/sample.yaml
   ```
   You should see a risk score output and a findings list. If this works, you're ready.

### Step 2: Set Up a Test Account on Each Platform

You will test against **real platforms using their official developer/sandbox APIs**. Create **fresh throwaway accounts** for this — do not use personal or production accounts.

**Platforms to target (in order of ease):**

| Platform | Why It's Good | What to Sign Up For |
|---|---|---|
| **Slack** | Most over-permissioning examples documented publicly | Free Slack workspace + create a test App at api.slack.com |
| **GitHub** | Well-documented scope hierarchy, known broad scopes | Free account + create a Personal Access Token or OAuth App |
| **Google (Gmail/Drive)** | Largest scope list (300+), documented over-permissioning | Google Cloud Console → new project → OAuth credentials |
| **Notion** | Simpler API, easy to isolate scope behavior | Free account + create an integration at notion.so/my-integrations |
| **Trello** | Basic API key + token, easy to manipulate | Free account + get API key from trello.com/app-key |

Sign up for **at least 3** of the above.

---

## Phase 2 — Understand What "Over-Permissioning" Looks Like on Each Platform

These are **real, documented, publicly known** patterns — not secret exploits. You are testing whether your tool *detects* them.

### Slack
- **Scope:** `channels:read` — should only list channels
- **Known issue:** Some API endpoints (e.g., `conversations.history`) accessible even when only `channels:read` is granted in certain legacy app configurations
- **What to test:** Request `conversations.history` with a token that only declared `channels:read`. Does the API return data? Your tool should flag this as scope divergence.
- **Reference:** Slack's own docs note that bot token vs user token scopes behave differently — a bot token with `channels:read` may still expose DM metadata via certain endpoints

### GitHub
- **Scope:** `repo` — this is famously over-broad. It grants read/write to ALL repositories including private ones
- **Known issue:** Apps requesting `repo` when they only need `public_repo` is a documented over-permissioning pattern (GitHub themselves warn about this in their docs)
- **What to test:** Create an OAuth App that declares only `public_repo`. Then attempt to access a private repo endpoint via your fuzzer. Does GitHub return a 404 (correct) or 200 (scope violation)?
- **Reference:** GitHub OAuth Scopes docs explicitly flag this: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps

### Google APIs
- **Scope:** `https://www.googleapis.com/auth/gmail.readonly` — should only read emails
- **Known issue:** Apps historically request full `https://www.googleapis.com/auth/gmail` (read + write + delete) when readonly suffices
- **What to test:** Use a token with `gmail.readonly`. Attempt a `messages.delete` or `messages.send` via your fuzzer. Should get 403. If it doesn't, that's a finding.
- **Reference:** Google's OAuth 2.0 Playground (oauth2.googleapis.com/tokeninfo) lets you inspect what a token actually grants

### Notion
- **Scope:** Notion integrations use "capabilities" — Read content / Update content / Insert content
- **What to test:** Create an integration with only "Read content." Attempt a PATCH request to update a page via your fuzzer. Should get 403.

### Trello
- **Scope:** `read` vs `write` tokens
- **What to test:** Get a read-only token. Attempt a POST to create a card via your fuzzer. Flag if it succeeds.

---

## Phase 3 — Write Test Case YAML Files for Each

Your prototype uses YAML config files to define test cases. Create one file per integration. Here's the exact format to follow (adapt to your actual schema):

```yaml
# test_cases/slack_channels_read.yaml
integration_name: "Slack Bot - channels:read scope"
platform: "Slack"
declared_scopes:
  - "channels:read"
base_url: "https://slack.com/api"
auth:
  type: "bearer"
  token: "YOUR_SLACK_BOT_TOKEN_HERE"
taint_seed:
  type: "synthetic_user_id"
  value: "AIT_TEST_USER_7x92k"
test_cases:
  - name: "Scope boundary: conversations.history access"
    endpoint: "/conversations.history"
    method: "GET"
    params:
      channel: "YOUR_TEST_CHANNEL_ID"
    expected_behavior: "denied"   # should be blocked given declared scope
    severity_if_violated: "High"

  - name: "Scope boundary: users.list access"
    endpoint: "/users.list"
    method: "GET"
    expected_behavior: "denied"
    severity_if_violated: "Medium"
```

Create a separate YAML file for each platform:
- `slack_channels_read.yaml`
- `github_public_repo.yaml`
- `google_gmail_readonly.yaml`
- `notion_read_only.yaml`
- `trello_read_token.yaml`

---

## Phase 4 — Run the Auditor and Collect Raw Output

### For each YAML file, run:
```bash
python run_audit.py --config test_cases/slack_channels_read.yaml --output results/slack_output.json
```

### From each output JSON, note down:
1. **Finding type** — what kind of violation was detected (hidden access, sensitive data exposure, scope divergence)
2. **Risk score** — the number your system outputs (formula: `min(100, 25×hidden + 20×sensitive + 15×divergence)`)
3. **Severity** — Critical / High / Medium / Low
4. **Response code received** — 200 (violation), 403 (correctly blocked), etc.
5. **Taint trace** — did your synthetic data appear in a response it shouldn't have?
6. **Time to detect** — milliseconds from request to finding

Do this for every test case across all platforms.

---

## Phase 5 — Organize Into Your Results Table

Once you have raw outputs, compile them into this table (this becomes **Table II** in the paper):

| # | Platform | Integration Scenario | Declared Scope | Violation Type | Risk Score | Severity | Detected? |
|---|---|---|---|---|---|---|---|
| 1 | Slack | Bot token over-access | `channels:read` | Hidden endpoint access | 80 | High | ✅ Yes |
| 2 | GitHub | PAT broad scope | `public_repo` | Private repo data exposure | 65 | High | ✅ Yes |
| 3 | Google | Gmail integration | `gmail.readonly` | Write operation not blocked | 45 | Medium | ✅ Yes |
| 4 | Notion | Read-only integration | Read Content | Update endpoint accessible | 55 | Medium | ✅ Yes |
| 5 | Trello | Read token | `read` | Card creation not blocked | 40 | Low | ✅ Yes |
| 6 | Slack | Compliant bot | `chat:write` | None | 0 | — | ✅ (No FP) |
| 7 | GitHub | Compliant app | `read:user` | None | 0 | — | ✅ (No FP) |

> **The last 2 rows are critical** — they show your tool does NOT generate false positives on compliant integrations. This proves precision.

### Calculate Your Precision:
```
Precision = True Positives / (True Positives + False Positives)
         = 5 / (5 + 0)
         = 100%
```

Even 3 true positives and 0 false positives = 100% precision. That's a strong result.

---

## Phase 6 — Write the Numbers Into the Paper

Once you have your table, fill in these specific spots in the draft:

### Abstract (replace placeholders):
> "Evaluation across **[5–7] integrations** on **[3–5] platforms** demonstrates detection of **[X] unauthorized access patterns** with **[Y]%** precision."

### Section VI — Evaluation:
- Paste your Table II
- Add a paragraph: *"Across N integrations tested, AIT identified M scope violations. Risk scores ranged from X to Y (mean: Z). The system produced zero false positives on compliant integrations, yielding 100% precision on the controlled test set."*
- Show one worked risk score calculation step-by-step (you already have this in the draft)

### Section VII — Limitations:
Add: *"The current evaluation is conducted on a controlled test set of N integrations. Large-scale empirical evaluation across production deployments is reserved for future work."*  
This preempts the reviewer's "small dataset" criticism by acknowledging it yourself.

---

## Phase 7 — Verify Your Results Are Defensible

Before handing results to the team, answer these questions:

- [ ] Can you re-run the tests and get the same scores? (Reproducibility)
- [ ] Are all test tokens/credentials from accounts YOU created and control?
- [ ] Did you test at least one compliant integration (to prove no false positives)?
- [ ] Is every result explainable — can you point to exactly which API call caused which finding?
- [ ] Are the declared scopes taken from the official platform documentation?

If yes to all → your results are solid and defensible to a reviewer.

---

## Deliverable Checklist (What You Hand to the Team)

```
results/
├── slack_output.json
├── github_output.json
├── google_output.json
├── notion_output.json
├── trello_output.json
├── results_table.csv        ← the Table II data
└── precision_calculation.txt ← TP, FP, FN counts + formula
```

Plus a short note to your team:
> "Tested X integrations across Y platforms. Found Z violations. Precision: N%. All results in /results folder. Replace Table II in the draft with results_table.csv."

---

## Timeline

| Day | Task |
|---|---|
| Day 1 | Set up test accounts on Slack, GitHub, Google |
| Day 2 | Write YAML test case files for all 5 platforms |
| Day 3 | Run auditor, collect raw JSON outputs |
| Day 4 | Compile results table, calculate precision |
| Day 5 | Hand results + filled-in table to paper team |

**5 days total. This is realistic with a working prototype.**

---

## If Your Prototype Has Bugs / Doesn't Run

If the code doesn't work out of the box:

1. Run it against the existing toy FastAPI server first (don't jump to real APIs)
2. Fix one microservice at a time — start with just the Differential Fuzzer in isolation
3. Even if taint tracking doesn't work, the scope divergence detection alone (did the API return 200 when it should return 403?) is enough for a result
4. **Minimum viable result:** A script that sends a request to an API with a restricted token and checks if the response code is unexpected. That IS your tool working, even in simplified form.

---

*Good luck. The results section is the only thing between your draft and a submission.*
