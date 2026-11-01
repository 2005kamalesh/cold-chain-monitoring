# AI use disclosure

## Tools
- **Claude (Anthropic)** in the claude.ai chat: wrote almost all of the code, tests and documents in this repository from the assignment text and my instructions.
- **Another AI assistant** (earlier chat, see `prompt_history.md` section A): used only to understand the assignment and choose a plan and tech stack. No code from it is in the repository.

## Where AI sped up the work
- Reading the assignment and turning it into a list of tables, rules and edge cases.
- Writing the data generator, the monitoring engine, the validation and evaluation code, the API and the dashboard.
- Writing the tests, the reports and the documents.
- Explaining Git, MySQL setup and error messages.

## Where I relied on it heavily
Nearly all of the implementation was written by Claude. I gave the direction (an MVP, Python with FastAPI and Streamlit, SQLite or MySQL, then the full 1,000 shipment volume, then the GitHub documents) and Claude produced the code and files. I did not write the core logic by hand.

## What I did myself
- Ran the project on my own machine (Windows, SQLite) and checked the API output at `/dashboard/summary` against the numbers in the reports.
- Found and reported a dashboard crash in the Shipment monitoring page, which led to a fix.
- Questioned why some dashboard tabs were empty and checked the explanation using a shipment with a known policy error (SHP-2026-000005).
- Compared the deliverables with the assignment text and the submission rules, and asked for changes (shorter README, removing the license file, adding documents).
- Set up the GitHub repository and checked `git status` before pushing.
- [EDIT: add anything else that is true, for example parts of the code you read or changed yourself]

## How the AI's work was checked
- The project checks itself: 85 validation checks, 16 tests, a comparison of the engine's results with a separate ground truth file, and a same-seed repeat run (`docs/validation_report.md`, `docs/evaluation_report.md`, `docs/reproducibility_report.md`).
- One mistake was found this way: the generator sometimes picked the correct product for the "wrong product" test case. The evaluation showed one missed case, and the generator was fixed.
- These checks were run by Claude in its own environment. I re-ran the pipeline and the API on my machine.

## Limits of this disclosure
- The MySQL option and the Streamlit and FastAPI code were not run by Claude (its environment could not install those libraries). I ran the dashboard and API myself on SQLite. MySQL has not been tested.
- The prompt record has gaps, described in `prompt_history.md`.
