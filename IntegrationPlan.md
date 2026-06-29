# Integration Plan — SOLID Refactor Merge & Final Quality Gates

## Branch
`refactor/integration-solid`

## Goal
Merge Agent 1 and Agent 2 branches, resolve cross-layer wiring, clean up test duplicates, and land the codebase with **no SOLID grade below B**.

## Pre-requisites
- Agent 1 branch `refactor/agent-solid-domain-app` passes its acceptance criteria.
- Agent 2 branch `refactor/agent-solid-infra-interface` passes its acceptance criteria.

## Merge strategy
1. Create `refactor/integration-solid` from the current `development` tip.
2. Merge `refactor/agent-solid-domain-app` into `refactor/integration-solid`.
3. Merge `refactor/agent-solid-infra-interface` into `refactor/integration-solid`.
4. Resolve any file-level conflicts in `routes.py`, `application/services/__init__.py`, and test fixtures.

## Tasks

### 1. Update the composition root (`src/brief_scout/main.py`)
- Wire `CompletenessChecker` into `BriefGenerationPipeline`:
  ```python
  pipeline = BriefGenerationPipeline(
      intake_use_case=intake_use_case,
      research_pipeline=research_pipeline,
      synthesis_use_case=synthesis_use_case,
      storage=storage,
      completeness_checker=completeness_checker,
  )
  ```
- Replace the hard-coded search-tool branch with `SearchToolFactory`:
  ```python
  from brief_scout.infrastructure.factories import SearchToolFactory

  search_tool = SearchToolFactory().create(config.app_config.search)
  ```
- Store a `BriefMarkdownRenderer` instance on `app.state`:
  ```python
  from brief_scout.application.services.brief_markdown_renderer import BriefMarkdownRenderer

  brief_markdown_renderer = BriefMarkdownRenderer()
  app.state.brief_markdown_renderer = brief_markdown_renderer
  ```
- Ensure the infrastructure `Jinja2TemplateRenderer` is passed everywhere a `TemplateRenderer` is now required (`IntakeDataExtractor`, `JourneyAcknowledgementService`).

### 2. Resolve domain/application type moves
- Verify `src/brief_scout/domain/ports/__init__.py` exports `ResearchStep`, `PipelineEvent`, and the runtime-checkable ports.
- Update any lingering imports in `application/services/`, `interfaces/api/`, or tests that still point to the old application locations.

### 3. Consolidate test doubles (`tests/conftest.py`)
- Replace the inline `FakeLLMAdapter`, `InMemoryStorageAdapter`, `CompletenessChecker`, and `LocalFileTelemetryAdapter` duplicates with the production adapters or thin wrappers.
  - Use `brief_scout.infrastructure.llm.fake_llm_adapter.FakeLLMAdapter` for `fake_llm`.
  - Use `brief_scout.infrastructure.storage.in_memory_adapter.InMemoryStorageAdapter` for `storage`.
  - Use `brief_scout.domain.services.completeness_checker.CompletenessChecker` for completeness checks.
  - Use `brief_scout.infrastructure.telemetry.local_file_adapter.LocalFileTelemetryAdapter` for `telemetry`.
- Keep the `FakeLLMAdapter` call-log helper by wrapping the production adapter if needed.

### 4. Finalize route wiring
- Confirm `interfaces/api/routes.py` uses `Depends(get_brief_markdown_renderer)` and that `dependencies.py` reads from `request.app.state.brief_markdown_renderer`.
- Confirm `send_message` and `run_pipeline` inject and use the renderer.

### 5. Regenerate demo output
- Run `uv run python scripts/run_demo.py` to regenerate `demo_conversation.md`.
- Verify the regenerated transcript contains the full Nike brief.

### 6. Documentation updates
- Update `AGENTS.md` or `README.md` if the architecture changes affect how adapters are added (search-tool registry, storage registry).
- Add a short note about the new factory registries.

## Final quality gates
Run the full suite and verify:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest --cov=src/brief_scout --cov-report=term-missing -q
```

- All tests pass.
- Coverage ≥ 93% (current baseline).
- No new ruff or mypy errors.

## SOLID acceptance checklist
Before merging to `development` and `main`, confirm:

| Principle | Grade | Evidence required |
|-----------|-------|-------------------|
| SRP       | ≥ B   | No duplicated renderer; `IntakeData` has one reason to change; routes are thin. |
| OCP       | ≥ B   | New search/storage providers added by registry entry only; no `if/else` in composition root. |
| LSP       | ≥ B   | `@runtime_checkable` ports; fake adapter raises on bad structured fixtures. |
| ISP       | ≥ B   | Narrow ports used where possible; no bloated interfaces forced on clients. |
| DIP       | ≥ B   | No domain port imports application/infrastructure; dependencies point inward. |

## Merge to trunk
1. Fast-forward merge `refactor/integration-solid` into `development`.
2. Merge `development` into `main` (or fast-forward `main` to the integration tip).
3. Push both `development` and `main` to `origin`.

## Rollback plan
If the final gates fail and cannot be fixed within one hour:
- Revert `refactor/integration-solid` merge in `development`.
- Keep `main` unchanged at the pre-refactor commit.
- Open follow-up issues for each unresolved SOLID violation.
