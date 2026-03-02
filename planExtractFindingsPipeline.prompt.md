## Plan: Unblock Finding Extraction Pipeline (DRAFT)

The pipeline is healthy up to source collection, but extraction is still producing zero findings due to brittle output-shape handling and weak persistence verification. Discovery shows the highest-probability failures are in extraction parsing/schema drift and missing post-save checks for findings. The plan below applies your requested fixes directly in the Researcher extraction path and adds DB-state verification in the orchestrator, with minimal blast radius. This keeps your current architecture intact while making extraction resilient to real LLM outputs and ensuring findings cannot silently disappear between phases.

**Steps**
1. Harden extraction payload diagnostics in [app/agents/researcher.py](app/agents/researcher.py#L393-L570) inside `_extract_from_batch`: add loud per-source/per-batch logs (content length, empty ratio, prompt length), and explicit warning when first source text length is low.
2. Replace cleaner with robust `clean_json_string` behavior in [app/agents/researcher.py](app/agents/researcher.py#L573-L593): strip markdown wrappers/preamble, isolate first `[` to last `]`, attempt balanced extraction, and log raw LLM output on parse failure before fallback.
3. Tighten extraction prompt in [app/agents/researcher.py](app/agents/researcher.py#L465-L488): require 1–3 factual findings, flat JSON array only, no prose/markdown, explicit empty-array rule when none found.
4. Make parser tolerant to schema drift in [app/agents/researcher.py](app/agents/researcher.py#L523-L558): accept `finding|content|fact|insight` and `sources|source_ids|source_id`, and record parse mode used for debugging.
5. Verify findings persistence after researcher phase in [app/agents/orchestrator.py](app/agents/orchestrator.py#L215-L246) and [app/agents/orchestrator.py](app/agents/orchestrator.py#L467-L523): compare extracted vs persisted counts using `FindingRepository.count_by_research`, warn/fail fast when extracted > 0 but persisted is 0, and add a single retry path for findings insert.
6. Add downstream guardrails (no behavior change) in [app/agents/analyst.py](app/agents/analyst.py#L80-L99) and [app/agents/fact_checker.py](app/agents/fact_checker.py#L84-L97): log loaded findings count with session id so zero-state origin is immediately visible.

**Verification**
- Run one full query and confirm logs show: non-empty extraction payload metrics, parse mode, and non-zero parsed findings.
- Confirm DB counts after Phase 2: findings persisted > 0 for same session id.
- Confirm Phase 3/4 logs load non-zero findings.
- Re-run `pytest tests/ -v` and a targeted extraction flow check.

**Decisions**
- Chose minimal surgical edits over redesign to preserve current agent workflow.
- Chose tolerant parser plus strict prompt (both) because prompt-only fixes are insufficient with real model variance.
- Chose persistence verification at orchestrator boundary so failures are caught exactly where handoff occurs.
