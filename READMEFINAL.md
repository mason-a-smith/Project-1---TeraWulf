# TeraWulf — Project 1 final working bundle

**Start here:** [Decision memo](06_Decision_Memo.md) · [Edition B with before/after evolution](02_Edition_B.md) · [Visible model results](outputs/VISIBLE_OUTPUT.html) · [Updated timed scripts](videos/PROJECT1_VIDEO_SCRIPTS_UPDATED.docx) · [Video 1 short script](videos/VIDEO_1_RESEARCH_EVOLUTION_UNDER_3_MIN.md) · [Video 1 visual deck](videos/VIDEO_1_RESEARCH_EVOLUTION_UNDER_3_MIN_VISUAL.pptx) · [Video 2 visual deck](videos/VIDEO_2_CODE_VALIDATION_VISUAL.pptx) · [Recording guide](VIDEO_RECORDING_GUIDE.md)

Committee action: **watch/defer;0% allocation**. Conditional contracted-project range approximately $0–$2.75/share. This is a retrospectiveJune30, 2026 valuation using later evidence, not an October spot target. Original coursework files remain untouched outside this folder; supplied Edition A is byte-identical.

## Use the product

On this Windows machine, double-click **START_WORKBENCH.cmd**, then open **http://127.0.0.1:8765**. In a terminal from this folder, use `uv run --no-project python app/server.py`; if Python is on PATH, `python app/server.py` also works. Python3.10+; validated with3.13.15. No third-party packages, paid services, hosting, account or internet connection is required once Python is installed.

Change a bounded slider and press Run inputs. Read the result against the base. Reset base restores all inputs. Demonstrate funding failure sets the assumed new facility tozero and shows failed cash/funding checks with valuation withheld. Reset to recover. Never edit engine.py to make a failing check disappear.

If port8765 is busy, run `python app/server.py --port 8767` and open that port. When viewing index.html directly from disk, live calculations cannot run; use the server. The static visible-output HTML opens without a server and contains all material results.

## Reproduce and freeze

1. `python app/validate.py` — finance and failure checks, writes actual test log.
2. `python app/build.py` — regenerates results, statement CSV, peer table and assumption record.
3. `python app/cold_run.py` — creates a fresh no-pip venv and copied bundle, rebuilds and tests HTTP behavior; retains the temporary environment beside the bundle for audit.
4. `python app/freeze.py` — updates hashes after approved changes/recordings. `python app/freeze.py --verify` checks them.

Prefix with `uv run --no-project` if the machine lacks a Python command. No model inputs are fetched at runtime. Source/assumption changes require explicit evidence review, tests, regeneration and a new freeze.

## Provisional seven-part submission map

The official shared filename checklist was not supplied. These names are organized consistently but must be mapped to that checklist before submission.

| Part | Deliverable | Location / status |
| --- | --- | --- |
|1|Unchanged Edition A|01_Edition_A_UNCHANGED.md; receipt still needed|
|2|Edition B|02_Edition_B.md; complete analytical draft|
|3|Repository / visible output|app/, evidence/, outputs/, validation/, README, MANIFEST; runnable locally|
|4|Research-evolution Video 1|videos/04_Research_Evolution.mp4 + corrected transcript pending; 2:50 script and matching five-slide visual deck supplied|
|5|Code/validation Video 2|videos/05_Code_Validation.mp4 + corrected transcript pending; matching six-slide visual deck supplied|
|6|Decision memo|06_Decision_Memo.md and print-formatted HTML; concise technical appendix in evidence/|
|7|Committee Video 3 + frozen record|videos/07_Committee_Defense.mp4 + corrected transcript pending;07_AI_USE_AND_VALIDATION.md complete disclosure; PROJECT1_VIDEO_SCRIPTS_UPDATED.docx contains current timed scripts; Video 3 opens with required live demo|

## Coverage and remaining human/course evidence

The financial/product build covers normalized history, five full pro-forma years, signed FCFF/DCF, WACC/g grid, causal scenarios, reverse price hurdle, two peer multiples, transaction qualification, OAT range-dependence, bounded controls, failed-check recovery, source register and reproducible outputs.

**Not submission-complete until authentic missing items are added:** Edition A Brightspace receipt; published training-case answers and their comparison; original human AI-off changed-input precommit; named partner feedback; actual videos and corrected transcripts; official filenames/duration limits; final upload/access receipt. The user was asked for these; none is fabricated or replaced by an AI narrative. The AI-authored directional test is not the human-only record. If the historical record does not exist, obtain instructor remediation rather than backdating it.

**Visual QA limitation:** browser checks on the updated workbench verified the nine sections, model controls, failure/recovery and a 390px viewport with no horizontal overflow. Camera rehearsal, final print pagination and actual video/transcript review remain pending. No test is described as a completed student recording.

## Research evolution preserved

Edition A → early reverse DCF (wulfdcf.md) → peer P/E rejection → September 24 company-specific statements/assumptions → September 29 OAT → final unified workbench. Prior artifacts are copied to evidence/for comparison, not used as independent validation. Generic ABG/dealer exercises are excluded from the WULF engine.

The project interprets “all available information” as the supplied local coursework plus reviewed primary disclosures through the stated cutoff. It does not claim access to unsupplied class feedback, private conversations, Brightspace, or every document ever published by the issuer.
