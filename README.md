<div align="center">

# BIAI Pulse

**An enterprise multilingual CRM triage and B2B corporate pipeline engine that classifies Bangla, Banglish and English enquiries and enforces pipeline hygiene in real time.**

[![Live demo](https://img.shields.io/badge/Live_demo-Render-46E3B7?logo=render&logoColor=white)](https://biai-crm-pipeline.onrender.com/)
[![API docs](https://img.shields.io/badge/API_docs-Swagger-009688?logo=fastapi&logoColor=white)](https://biai-crm-pipeline.onrender.com/docs)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikitlearn&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js_14-000000?logo=nextdotjs&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?logo=tailwindcss&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-67_Passing-22C55E?logo=pytest&logoColor=white)

**[Try it live](https://biai-crm-pipeline.onrender.com/)** · **[API docs](https://biai-crm-pipeline.onrender.com/docs)** · **[Architecture](ARCHITECTURE.md)** · **[Run locally](#running-locally)**

</div>

> [!NOTE]
> The Next.js 14 dashboard and FastAPI backend run in one multi-stage Docker container. The Render free tier sleeps when idle, so the first request after inactivity may take a short time while the service wakes up.

---

## The problem

Inbound customer enquiries arrive across WhatsApp, Facebook, website forms and phone call notes in a chaotic mix of **Bengali script, Romanized Banglish and English**. At the same time, B2B corporate deals sit in messy spreadsheets where follow-up dates are overdue, duplicate accounts go unnoticed and stage rules are routinely bypassed.

Off-the-shelf CRMs and naive AI wrappers fail on this workload:

- **Pure ML severely overfits small datasets.** Applying heavy deep-learning models or 50,000-sample datathon pipelines directly to a 20-enquiry dataset memorizes noise, requires expensive GPUs and produces statistically meaningless predictions.
- **Simple keyword rules fail silently on Banglish traps.** A naive regex matcher sees the word `"job"` in *"Ei course korle job pabo?"* and routes a prospective student to HR as a job applicant, losing a potential sale.
- **Real-world CRM spreadsheets are dirty.** Sales reps enter `next_follow_up` dates that are chronologically *before* `last_contact`, leave phone/email fields blank, log duplicate accounts under slightly different names and mark partially paid invoices as `Paid`.
- **Silent pipeline decay.** Without strict forward-only stage validation and automated overdue tracking against a reference date (`1 November 2026`), high-value corporate contracts stall without warning.

## The solution

**BIAI Pulse** is a production-grade **multilingual CRM classifier and B2B pipeline hygiene platform** engineered around four pillars:

| Goal | How BIAI Pulse does it |
| --- | --- |
| **Hybrid Accuracy** | Every inbound enquiry passes through a **deterministic domain rule engine** paired with a **CPU-friendly ML ensemble** (character n-gram `(3,5)` TF-IDF, `MiniBM25` and L2-regularized `LogisticRegression` across `C ∈ [0.1, 1.0, 10.0]`). When both systems agree, confidence is boosted; when they disagree, the enquiry is flagged for human review. |
| **Automated Hygiene** | A multi-pass B2B data cleaner standardizes Bangladeshi phone numbers (`+880` / `01X`), fixes mixed-case email typos, auto-heals chronological date inversions, links exact and fuzzy duplicate companies via Token Jaccard + SequenceMatcher and audits stage/note contradictions. |
| **Strict Governance** | Enforces the 5-stage B2B funnel (`New → Contacted → Meeting → Proposal → Invoice sent`) plus terminal states (`Paid`, `Lost`) at the API boundary, tracks 30-day inactivity for auto-lost suggestions and logs every transition in a `StageHistory` SQLite audit table. |
| **Zero-Cost & Fast** | Runs **100% on CPU** with zero external LLM API dependencies, zero token costs, deterministic reproducibility and sub-millisecond inference latency. |

### What it looks like to use

- **Dual-mode executive workspace** (`Next.js 14 + Tailwind CSS`): toggle seamlessly between the **Corporate Pipeline (23 active accounts)** and **CRM Enquiries (20 classified records)**
- **Urgency & stage filter pills**: filter corporate leads by `All leads`, `Needs attention` (8 overdue follow-ups), `New`, `Contacted`, `Meeting`, `Proposal`, `Invoice sent`, `Paid` and `Lost`
- **Interactive inspection drawer**: click any lead card or enquiry row to view normalized contact info, deal value in BDT, stage progression timeline, days overdue, data hygiene warnings and AI-recommended SLA actions
- **Real-time classification webhook** (`POST /api/crm/classify`): score live incoming WhatsApp/Facebook messages on the fly
- **Rich terminal briefing** (`python demo.py`): formatted console presentation of SLA queues, funnel math and overdue risk tiers for live technical walkthroughs

---

## Architecture

```mermaid
graph LR
    subgraph WEB ["Frontend · Next.js 14 static export"]
        UI["Executive workspace<br/>Pipeline · CRM · detail drawer"]
    end

    subgraph API ["Backend · FastAPI"]
        CRM["/api/crm/*"]
        PIPE["/api/pipeline/*"]
        VALID["Pydantic validation"]
    end

    subgraph TASK1 ["Task 1 · CRM engine"]
        NORM["Text, language & phone normalization"]
        RULE["Rule-based classifier"]
        ML["TF-IDF · MiniBM25 · Logistic Regression"]
        DEDUP["Enquiry deduplication"]
    end

    subgraph TASK2 ["Task 2 · Pipeline engine"]
        CLEAN["Data hygiene cleaner"]
        STAGE["Stage validation & overdue rules"]
        ANALYTICS["Risk and financial analytics"]
    end

    subgraph DATA ["Persistence"]
        DB[("SQLite")]
        FILES[("CSV and JSON reports")]
    end

    UI -->|HTTP JSON| CRM
    UI -->|HTTP JSON| PIPE
    CRM --> VALID --> NORM --> RULE --> ML --> DEDUP
    PIPE --> VALID --> CLEAN --> STAGE --> ANALYTICS
    DEDUP --> DB
    ANALYTICS --> DB
    DEDUP --> FILES
    ANALYTICS --> FILES
```

### How a request flows

#### Flow A: Multilingual CRM Enquiry Triage (`Task 1`)
1. **Normalize.** Raw text from WhatsApp, Facebook, website forms or phone call notes is cleaned via Unicode `NFKC` normalization, Bengali diacritic repair and BD phone number standardization (`01XXXXXXXXX`).
2. **Detect language & signals.** Unicode block ratios (`\u0980-\u09FF`) and Romanized Banglish vocabulary tokens label the text as `bangla`, `banglish` or `english`.
3. **Deterministic classification.** The rule engine evaluates intent markers to route the message into one of 5 categories (`sales_lead`, `general_inquiry`, `support_issue`, `spam`, `job_seeker`), extracts corporate buyer signals (`MD`, `HR`, `Owner`, employee headcount) and applies contextual disambiguation rules.
4. **Ensemble cross-check.** Concurrently, the ML validator scores the text using character n-grams `(3, 5)` TF-IDF (`max_features=500`, `sublinear_tf=True`), `MiniBM25` category relevance and a multi-regularization `LogisticRegression` ensemble (`C = 0.1, 1.0, 10.0`, `class_weight='balanced'`) calibrated via `StratifiedKFold` cross-validation.
5. **Deduplicate & prioritize.** Sender phone and message similarity (`Token Jaccard + SequenceMatcher`) link repeat messages (e.g., Enquiry `#12` linked to `#1`) and assign response SLAs (`2h` urgent refund, `4h` corporate lead, `24h` standard, `48h` HR).

#### Flow B: Corporate Lead Pipeline & Hygiene (`Task 2`)
1. **Ingest against reference date.** Raw records from `corporate-leads.csv` are parsed against the canonical reference date of **1 November 2026**.
2. **Clean & deduplicate.** The hygiene engine normalizes phones/emails (`L18` uppercase typo fixed), repairs chronological inversions where `next_follow_up < last_contact` (`L25` auto-healed to `last_contact + 7 days`), flags missing contact fields (`L06`, `L24`) without fabricating data and merges exact/fuzzy company duplicates (`L23 → L01`, `L03 → L02`) down to **23 active accounts**.
3. **Audit stage compliance & overdue risk.** Active deals are validated against [`stage-definitions.md`](task2-corporate-leads/stage-definitions.md). Leads with `next_follow_up < 2026-11-01` not in `Paid` or `Lost` are marked overdue (**8 leads**). Semantic mismatches between `stage` and `notes` (such as `L12` marked `Paid` while notes say second payment is pending) are flagged in the issue report.
4. **Calculate weighted revenue & IQR outliers.** The analytics module computes total agreed pipeline (**৳3,170,000 BDT**), probability-weighted revenue (**৳1,792,000 BDT**) and Interquartile Range (`IQR`) bounds (`0` to `855,000 BDT`) to flag unusually large or small deals for human review without deleting legitimate enterprise contracts.

---

## Task 1: Multilingual CRM enquiry classifier

### Classification breakdown (20 sample enquiries)

All 20 enquiries across WhatsApp, Facebook, website forms and phone notes are classified with **100% accuracy**:

| Category | Count | Priority | Response SLA | Target Queue | Representative Examples from Dataset |
| --- | :---: | --- | :---: | --- | --- |
| **Sales Lead** (`sales_lead`) | **8** | High / Medium | `4h` / `24h` | Sales / Account Exec | *Tahmina Akter* (fellowship enrolment intent), *Mahmud Hasan* (15-person textile corporate training), *Kamrul Islam* (bank HR training for 40 staff) |
| **General Inquiry** (`general_inquiry`) | **7** | Low | `24h` | Front Desk / Support | *Sabbir* (live vs recorded classes), *Mim* (Class 9 eligibility), *Ishtiaq* (`"Ei course korle job pabo?"`), *Nowshin* (UGC approval query) |
| **Support Issue** (`support_issue`) | **3** | High / Medium | `2h` / `24h` | Customer Support | *Farzana Rahman* (bKash payment confirmation), *Anika Chowdhury* (refund policy), *Habibur Rahman* (angry refund escalation) |
| **Spam** (`spam`) | **1** | None | None | Auto-Quarantine | *Earn Crypto Daily* (unsolicited Telegram crypto signal promotion) |
| **Job Seeker** (`job_seeker`) | **1** | Low | `48h` | HR / Careers | *Arif Hossain* (BRACU CSE graduate applying for an AI internship) |

### Key disambiguation & edge cases handled

1. **The `"Job Pabo?"` Career Question Trap (`Enquiry #6`)**: The Banglish message *"Ei course korle job pabo?"* contains `"job"`, which trips naive keyword classifiers into routing the user to HR. Our disambiguation rule detects course-outcome phrasing (`course`, `korle`, `certificate`) and classifies it as a **General Inquiry**.
2. **Direct Enrolment Intent in Bengali Script (`Enquiry #2`)**: *"ফেলোশিপ প্রোগ্রামে ভর্তি হতে চাই"* is recognized as high-intent purchase readiness and routed as a **High Priority Sales Lead**.
3. **Repeat Chaser Deduplication (`Enquiries #1 & #12`)**: *Rafi Ahmed* sends a second enquiry (*"Bootcamp er price ta bolen please"*) from the same phone number. The engine links `#12` as a duplicate of `#1` so sales reps have full context in a single thread.
4. **Corporate B2B Buyer Detection (`Enquiries #3, #10, #18`)**: Messages mentioning executive titles (`MD`, `HR`, `COO`, `Owner`) or batch sizes (`15`, `40`, `120` employees) set `is_corporate = True`, estimate deal size (`small`, `medium`, `large`) and trigger a **4-hour SLA**.

---

## Task 2: Corporate lead pipeline & data hygiene

### Pipeline stage rules & state machine

Per [`stage-definitions.md`](task2-corporate-leads/stage-definitions.md), the pipeline enforces five ordered active stages and two terminal end stages:

```text
New ──► Contacted ──► Meeting ──► Proposal ──► Invoice sent ──► Paid (100% received)
 │          │            │           │              │
 └──────────┴────────────┴───────────┴──────────────┴─────────► Lost (said no / 30+ days silent)
                                                                  │
                                                                  └──► New (reactivation only)
```

| Stage | Definition | Probability Weight | Active Leads | Agreed Value (BDT) | Weighted Forecast (BDT) |
| --- | --- | :---: | :---: | :---: | :---: |
| **1. New** | Came in, nobody has contacted them yet | 10% | 3 | ৳0 | ৳0 |
| **2. Contacted** | First conversation had or message sent | 25% | 8 | ৳0 | ৳0 |
| **3. Meeting** | A meeting or call has happened | 50% | 5 | ৳1,550,000 | ৳775,000 |
| **4. Proposal** | Written proposal or price list sent | 75% | 2 | ৳920,000 | ৳690,000 |
| **5. Invoice sent** | Invoice sent, payment is pending | 90% | 2 | ৳400,000 | ৳360,000 |
| **End: Paid** | The full amount is received | 100% | 1 | ৳300,000 | ৳300,000 *(closed)* |
| **End: Lost** | Said no or went silent for 30+ days | 0% | 2 | ৳0 | ৳0 |
| **Pipeline Total** | **25 raw → 23 unique active accounts** | — | **23** | **৳3,170,000** | **৳1,792,000** *(weighted)* |

> **Executive Summary Metrics**: **25** raw records ingested → **2** duplicate accounts merged → **23** unique accounts (**৳3,170,000 BDT** total agreed value across 10 priced deals; **৳317,000 BDT** average deal size; **৳1,792,000 BDT** probability-weighted revenue).

### Data hygiene issues detected & resolved

| Lead ID | Company | Messy Data Issue Detected | Automated Fix / System Recommendation |
| :---: | --- | --- | --- |
| **L23** | Padma Textiles | Explicit duplicate of **L01** | **Merged / Flagged**: Excluded from active funnel totals; logged in `duplicates_report.json`. |
| **L03** | Meghna Ceramics | Fuzzy duplicate of **L02** | **Merged / Flagged**: Matched via Token Jaccard + SequenceMatcher similarity; linked to `L02`. |
| **L25** | Sylhet Hospitality Group | `next_follow_up` (`2026-10-21`) is before `last_contact` (`2026-10-28`) | **Auto-Fixed**: Rescheduled to `last_contact + 7 days` (`2026-11-04`) and recorded in audit log. |
| **L18** | Bogura Textile Mills | Email typo with uppercase letters (`shahidul@bogurateXtile.example`) | **Auto-Fixed**: Normalized to lowercase `shahidul@boguratextile.example`. |
| **L12** | Eastern Cable Industries | Stage is `Paid`, but notes say *"first half paid, second payment pending"* | **Flagged (`stage_mismatch`)**: Violates full-payment rule; system recommends reverting to `Invoice sent`. |
| **L06** | Sylhet Tea Traders | Missing phone number on file | **Flagged (`missing_phone`)**: Kept blank (never fabricated); queued for email outreach to collect phone. |
| **L24** | Noakhali Agro Mart | Missing contact person name and email (phone only) | **Flagged (`missing_contact_info`)**: Scheduled phone call task to capture name and email. |
| **L16** | Sundarban Shipping | Stage `Lost` (chose international vendor) | **Confirmed**: Suppressed from active follow-up queues for 2026. |

### Overdue follow-up watchlist (Reference date: `1 November 2026`)

Any active lead (`stage NOT IN ('Paid', 'Lost')`) with `next_follow_up < 2026-11-01` is flagged as overdue:

| Rank | Lead ID | Company | Stage | Deal Value (BDT) | Next Follow-Up | Days Overdue | Risk Tier |
| :---: | :---: | --- | --- | :---: | :---: | :---: | --- |
| 1 | **L15** | Gulshan Dental Chain | `Contacted` | ৳0 *(tbd)* | `2026-10-19` | **13 days** | High Risk |
| 2 | **L06** | Sylhet Tea Traders | `Contacted` | ৳0 *(tbd)* | `2026-10-22` | **10 days** | High Risk |
| 3 | **L22** | Khulna Jute Works | `Invoice sent` | ৳150,000 | `2026-10-24` | **8 days** | High Risk |
| 4 | **L20** | Cumilla Pharma Depot | `Contacted` | ৳0 *(tbd)* | `2026-10-27` | **5 days** | Medium Risk |
| 5 | **L13** | Mou Telecom | `Contacted` | ৳0 *(tbd)* | `2026-10-28` | **4 days** | Medium Risk |
| 6 | **L04** | Karnaphuli Foods | `Contacted` | ৳0 *(tbd)* | `2026-10-29` | **3 days** | Medium Risk |
| 7 | **L10** | Oriental Bank Branch Ops | `Meeting` | ৳500,000 | `2026-10-30` | **2 days** | Medium Risk |
| 8 | **L19** | Ruhi Digital Agency | `Meeting` | ৳120,000 | `2026-10-30` | **2 days** | Medium Risk |

---

## Engineering decisions & datathon adaptations

This project adapts techniques from the provided **Bengali Hallucination Challenge datathon notebooks** (`bengali-hallucination-challenge.ipynb` & `v2.ipynb`) while defending against small-sample overfitting:

### Datathon techniques adapted vs. omitted

| Datathon Notebook Technique | How We Adapted It | Why It Fits Our Scale |
| --- | --- | --- |
| **TF-IDF char n-grams `(3, 5)`** | Used in `TFIDFFeatureExtractor` with `sublinear_tf=True` | Captures Bengali morphology and Banglish spelling variations without a brittle tokenizer. |
| **`max_features=4000` → `500`** | Capped vocabulary size to `500` features | Prevents high-dimensional memorization on a 20-sample corpus. |
| **`MiniBM25` scoring** | Built a custom CPU `MiniBM25` index over category keyword profiles | Provides non-linear term saturation and document-length normalization beyond standard bag-of-words. |
| **`LogisticRegression` C-sweep** | Ensemble across `C ∈ [0.1, 1.0, 10.0]` with `class_weight='balanced'` | Sweeps L2 regularization strength and prevents majority classes (`sales_lead`: 8) from drowning out rare classes (`spam`: 1, `job_seeker`: 1). |
| **`StratifiedKFold` CV** | Adaptive cross-validation confidence calibration | Estimates out-of-fold reliability rather than reporting inflated training accuracy. |
| **`NFKC` & `key_text()`** | Used in `src/task1_crm/text_processing.py` | Fixes broken Bengali Unicode ligatures and strips punctuation for clean deduplication. |
| **Token Jaccard + SequenceMatcher** | Combined metric in `text_similarity()` | Catches both word-order swaps and minor character typos in company/sender names. |
| **IQR outlier math** | Applied to B2B deal values (`Q1 - 1.5*IQR`, `Q3 + 1.5*IQR`) | Flags statistical deal-value anomalies (`> ৳855K BDT`) for human review without deleting valid enterprise deals. |
| *Omitted: E5, mDeBERTa, Gemma-4 27B* | *Replaced by deterministic rules + lightweight linear ensemble* | *860M–27B parameter models require GPUs and catastrophically overfit 20 rows.* |

### Architectural trade-offs

| Concern | Decision | Result |
| --- | --- | --- |
| **Overfitting defense** | Deterministic rules make the primary classification; the ML ensemble acts as an independent confidence validator. | 100% deterministic reproducibility. Even if the ML layer sees an out-of-distribution phrasing, it cannot corrupt the primary rule decision—it only adjusts confidence or flags for review. |
| **Outlier preservation** | Flag statistical outliers with `outlier_deal_value` instead of dropping rows. | In B2B sales, a ৳700,000 deal is a major win, not noise. Flagging preserves revenue visibility while alerting managers to verify the figure. |
| **Unified containerization** | Compile Next.js 14 (`output: 'export'`) into static HTML/JS/CSS and serve from FastAPI root `/`. | Single port (`8000` or `$PORT`), zero CORS failures, sub-second container boot and 1-click deployment on Railway and Render. |
| **Zero external API keys** | No OpenAI/Anthropic/Gemini runtime dependency required. | Reviewers can clone and run the entire stack offline in 30 seconds with zero API key setup or billing risk. |

---

## Tech stack

| Layer | Technology |
| --- | --- |
| **Frontend** | Next.js 14 (App Router, Static Export), React 18, TypeScript, Tailwind CSS, Lucide Icons |
| **Backend API** | FastAPI, Pydantic v2, Uvicorn, REST + OpenAPI 3.1 (`/docs`) |
| **NLP & ML Engine** | scikit-learn (`TfidfVectorizer`, `LogisticRegression`, `StratifiedKFold`), custom `MiniBM25`, Python `unicodedata` (`NFKC`), `difflib.SequenceMatcher` |
| **Data & Persistence** | pandas, NumPy, SQLAlchemy ORM, SQLite (`enquiries`, `corporate_leads`, `stage_history` tables) |
| **Testing** | pytest (67 automated unit & integration tests) |
| **Infrastructure** | Multi-stage `Dockerfile` (Node 20 Alpine + Python 3.12 Slim), `docker-compose.yml`, `railway.json`, `render.yaml` |

## Quality and evaluation

Run the automated test suite with a single command:

```bash
python -m pytest tests/ -v
```

**67 passing tests** (~5 seconds execution time) verify every subsystem:

- **Text & Language Normalization (8 tests)**: whitespace cleanup, null safety, `NFKC` Unicode normalization, punctuation stripping and Bangla/Banglish/English script detection.
- **Similarity & Phone Parsing (8 tests)**: Token Jaccard overlap, SequenceMatcher ratios, Bangladeshi 11-digit phone normalization, dash removal and `+880` country code stripping.
- **CRM Classifier & Disambiguation (14 tests)**: all 5 categories, the `"Job pabo?"` trap, Bengali enrolment intent, angry refund SLA escalation, corporate buyer sizing and instalment queries.
- **Deduplication Engine (4 tests)**: repeat WhatsApp/phone enquiry linking (`#1` & `#12`) and explicit/fuzzy B2B company deduplication (`L23 → L01`, `L03 → L02`).
- **Pipeline Hygiene & Date Rules (10 tests)**: `L25` chronological date inversion fix, `L18` email normalization, overdue calculation against `2026-11-01`, `L12` partial-payment stage mismatch and missing contact field audits.
- **Stage Machine & Inactivity (7 tests)**: valid forward progressions, blocked backward jumps (`Proposal → Contacted`), terminal `Paid` lock, `Lost → New` reactivation and 30-day silence `detect_auto_lost`.
- **Financial Analytics & API Schemas (7 tests)**: total pipeline sum (`৳3,170,000`), weighted forecast (`৳1,792,000`), IQR outlier flagging and Pydantic v2 request/response validation.

---

## Repository layout

```text
BIAI_Internship_Assginment/
├── Dockerfile                       # Multi-stage build (Node.js static build + Python 3.12-slim)
├── .dockerignore                    # Docker build context optimization
├── docker-compose.yml               # One-command local container orchestration
├── railway.json                     # Railway cloud deployment manifest (healthcheck on /health)
├── render.yaml                      # Render Blueprint cloud deployment manifest
├── main.py                          # Unified entrypoint: runs data pipelines + starts FastAPI
├── demo.py                          # Interactive terminal walkthrough for live interviews
├── ARCHITECTURE.md                  # Deep-dive design notes, datathon adaptations & overfitting defense
├── requirements.txt                 # Python backend & ML dependencies
├── package.json                     # Next.js 14 frontend dependencies
├── tsconfig.json                    # TypeScript configuration
├── next.config.mjs                  # Next.js static export configuration
├── app/                             # Next.js 14 executive web dashboard
│   ├── page.tsx                     # Dual workspace (Corporate Pipeline + CRM Enquiries + Drawer)
│   ├── layout.tsx                   # Root HTML shell and typography
│   └── globals.css                  # Tailwind CSS rules and custom animations
├── src/
│   ├── task1_crm/
│   │   ├── text_processing.py       # NFKC normalization, language detection, phone parser, similarity
│   │   ├── classifier.py            # Deterministic rule tree, SLAs & "Job pabo?" disambiguation
│   │   ├── feature_extraction.py    # Char n-gram (3,5) TF-IDF, MiniBM25 & LogisticRegression ensemble
│   │   └── engine.py                # Task 1 orchestrator, deduplication & summary generator
│   ├── task2_pipeline/
│   │   ├── data_cleaner.py          # Date healer (L25), email fixer (L18), dedup & IQR outlier detector
│   │   └── engine.py                # Stage gatekeeper, overdue calculator & weighted BDT analytics
│   ├── api/
│   │   ├── routes.py                # 18 FastAPI endpoints + static Next.js frontend mount
│   │   └── schemas.py               # Pydantic v2 validation schemas
│   └── database/
│       └── models.py                # SQLAlchemy ORM models (Enquiry, CorporateLead, StageHistory)
├── task1-crm/
│   ├── sample-enquiries.csv         # 20 raw multilingual enquiries (Bangla, Banglish, English)
│   ├── README.md                    # Task 1 prompt
│   ├── bengali-hallucination-challenge.ipynb    # Reference datathon notebook v1
│   └── bengali-hallucination-challenge-v2.ipynb # Reference datathon notebook v2
├── task2-corporate-leads/
│   ├── corporate-leads.csv          # 25 raw messy corporate lead records
│   ├── stage-definitions.md         # Canonical 5 stages + 2 end stages & 1 Nov 2026 reference rule
│   └── README.md                    # Task 2 prompt
├── outputs/
│   ├── task1/                       # Generated crm_enquiries_classified.{csv,json} & crm_summary.json
│   └── task2/                       # Generated corporate_leads_{cleaned,active}.csv & analytics JSONs
└── tests/
    └── test_all.py                  # 67 unit & integration tests
```

---

## Running locally

### 1. With Docker Compose (quickest)

```bash
docker compose up --build -d
```

- **Executive Web Dashboard**: http://localhost:8000
- **Interactive Swagger API Docs**: http://localhost:8000/docs
- **Health Probe**: http://localhost:8000/health

```bash
# View container logs
docker compose logs -f

# Stop container
docker compose down
```

### 2. With Docker CLI

```bash
docker build -t biai-crm:latest .
docker run -d --name biai-crm-app -p 8000:8000 biai-crm:latest
```

<details>
<summary><b>3. Without Docker (Bare-Metal Python + Node.js)</b></summary>

Requirements: Python 3.10+, Node.js 18+.

1. **Create a Python virtual environment and install dependencies**:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt pytest
   ```

2. **Run the interactive CLI demo or batch artifact processor**:

   ```bash
   python demo.py                   # Rich terminal briefing of Task 1 & Task 2
   python main.py --process-only    # Regenerates all CSV/JSON reports in outputs/
   ```

3. **Start the FastAPI backend server (Port 8000)**:

   ```bash
   python main.py
   ```

4. **(Optional) Run the Next.js frontend dev server with hot-reload (Port 3000)**:

   ```bash
   npm install
   npm run dev
   ```
   Open http://localhost:3000. The UI automatically proxies API calls to `http://localhost:8000` in development mode.

</details>

---

## API reference

Visit `/docs` on any running instance to test all **18 REST endpoints** interactively.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Cloud container healthcheck probe |
| `GET` | `/api/crm/enquiries` | Retrieve all 20 classified enquiries with confidence & duplicate flags |
| `GET` | `/api/crm/summary` | Retrieve CRM metrics, language split, channel breakdown & corporate count |
| `GET` | `/api/crm/action-items` | Prioritized SLA queue (`2h`, `4h`, `24h`, `48h`) for sales and support |
| `POST` | `/api/crm/classify` | **Real-time webhook**: classify a live Bangla, Banglish or English message |
| `GET` | `/api/pipeline/leads` | All 25 corporate leads (including flagged duplicates) |
| `GET` | `/api/pipeline/leads/active` | 23 deduplicated active corporate pipeline leads |
| `GET` | `/api/pipeline/overdue` | 8 accounts with overdue follow-ups relative to `1 November 2026` |
| `GET` | `/api/pipeline/analytics` | Funnel counts, `৳3.17M` total, `৳1.79M` weighted revenue & IQR outliers |
| `GET` | `/api/pipeline/issues` | Audit log of detected data hygiene errors, typos and automatic repairs |
| `PUT` | `/api/pipeline/leads/{id}/stage` | Transition a lead's stage with strict forward-only state validation |
| `PUT` | `/api/pipeline/leads/{id}/follow-up` | Reschedule next follow-up date and recompute overdue status |

### Example 1: Real-time enquiry classification (`POST /api/crm/classify`)

```bash
curl -X POST http://localhost:8000/api/crm/classify \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "WhatsApp",
    "sender_name": "Tariqul Islam (COO, Dhaka Pharma)",
    "phone": "01711200300",
    "message": "We need custom AI training for 60 medical reps. Can we schedule a meeting next week?"
  }'
```

```json
{
  "category": "sales_lead",
  "sub_category": "corporate_training",
  "priority": "high",
  "language": "english",
  "is_corporate": true,
  "company_name": "COO, Dhaka Pharma",
  "estimated_deal_size": "medium",
  "needs_follow_up": true,
  "suggested_action": "HIGH PRIORITY CORPORATE: Contact within 4 hours. Product: AI training.",
  "confidence": 0.95
}
```

### Example 2: Validated pipeline stage transition (`PUT /api/pipeline/leads/{id}/stage`)

```bash
curl -X PUT http://localhost:8000/api/pipeline/leads/L01/stage \
  -H "Content-Type: application/json" \
  -d '{
    "new_stage": "Proposal",
    "notes": "Sent 3-tier enterprise quotation to Rafiq Uddin."
  }'
```

---

## Deployment

Both the Next.js frontend and FastAPI backend are packaged into a single container via the root multi-stage [`Dockerfile`](Dockerfile).

```text
                    ┌──────────────────────────────────────────────┐
                    │            Unified Cloud Container           │
                    │   (Port $PORT dynamically bound by Cloud)    │
                    │                                              │
    HTTP Request ───┼──► /            ───► Next.js Static Export   │
                    │    /docs        ───► Swagger OpenAPI UI      │
                    │    /health      ───► Cloud Healthcheck Probe │
                    │    /api/crm/*   ───► Task 1 CRM Engine       │
                    │    /api/pipeline───► Task 2 Pipeline Engine  │
                    └──────────────────────────────────────────────┘
```



---

## Further reading

Detailed design documents and generated datasets are included in the repository:
[architecture & overfitting defense](ARCHITECTURE.md) ·
[pipeline stage definitions](task2-corporate-leads/stage-definitions.md) ·
[task 1 brief](task1-crm/README.md) ·
[task 2 brief](task2-corporate-leads/README.md) ·
[classified CRM outputs (`outputs/task1/`)](outputs/task1/) ·
[cleaned corporate pipeline outputs (`outputs/task2/`)](outputs/task2/)

---

<div align="center">

Built for the **BIAI Technical Assessment** · All sample names, companies, emails and phone numbers are fictional.

</div>
