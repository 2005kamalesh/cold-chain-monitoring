# AI use disclosure

## How the work was split
I planned the project and made the main decisions. AI helped me think it through, and then wrote most of the code. In short: **I decided what to build and with which tools, and AI did most of the typing.**

## Tools
- **Another AI assistant** (earlier chat, see `prompt_history.md`, section A): I used it to go through the assignment and plan the work: the phases, the time I had, and which database and frameworks to use. No code from it is in the repository.
- **Claude (Anthropic)** in the claude.ai chat (section B): wrote the code, tests and documents from my instructions.

## What I did
- **Planning.** I read the assignment, worked through it in the planning chat, and decided how to approach it: build a working MVP first, then scale to the full 1,000 shipments.
- **Tech stack.** I chose Python with pandas, a SQL database (MySQL or SQLite), FastAPI for the backend, Streamlit for the dashboard, and GitHub for the code. I wrote this stack in my own prompts (`prompt_history.md`, A2 and A3) before asking Claude to build it. Because I already had MySQL installed, I asked for it to be supported, and SQLite became the default so the project runs without setup.
- **Giving direction.** I gave Claude the assignment and my plan, then asked it to check every requirement and edge case, move to the full data volume, build the reports and the README, and cross-check against the submission rules. I also asked for changes: a shorter README, no license file, a plain-language explanation.
- **Running and testing.** I ran the project on my own machine (Windows, SQLite). I found a crash in the Shipment monitoring page and reported it, which led to a fix. I questioned why some dashboard tabs were empty, and checked the answer with shipment SHP-2026-000005. I compared the API summary on my machine with the numbers in the reports.
- **Publishing.** I set up the GitHub repository, checked `git status` so large files were not uploaded, and pushed the work.

## Where AI helped most
Nearly all of the implementation was written by Claude: the data generator, the monitoring engine, validation and evaluation, the API, the dashboard, the tests and the documents. It also explained Git, MySQL setup and error messages. I did not write the core logic by hand.

## How the work was checked
- The project checks itself: 85 validation checks, 16 tests, a comparison of the engine's results with a separate ground truth file, and a repeat run with the same seed (`docs/validation_report.md`, `docs/evaluation_report.md`, `docs/reproducibility_report.md`).
- One mistake was found this way. The generator sometimes gave a shipment its own product's limits when it was meant to give the wrong ones. The evaluation showed a missed case, and the generator was fixed.
- Claude ran these checks in its own environment. I re-ran the pipeline and the API on my machine.

## Limits
- The MySQL option and the FastAPI and Streamlit code were not run by Claude, because its environment could not install those libraries. I ran the dashboard and API on SQLite. MySQL has not been tested.
- The prompt record has gaps, described in `prompt_history.md`.