# Refactor Plan — Agent 1: Domain & Application Layer SOLID Cleanup

## Branch
`refactor/agent-solid-domain-app`

## Goal
Raise **SRP**, **DIP**, and **LSP** grades for the domain and application layers by:
1. Removing outward dependencies from domain ports.
2. Eliminating duplicate completeness logic.
3. Consolidating template-renderer ownership.
4. Making core ports runtime-checkable.

## Target SOLID lift

| Principle | Current | Target | How this wave contributes |
|-----------|---------|--------|---------------------------|
| SRP       | B+      | A-     | Remove `IntakeData.is_complete()` duplication; delete app-layer renderer duplicate. |
| OCP       | C+      | B      | Domain events/steps are stable abstractions; application services depend on injected renderer. |
| LSP       | C+      | B      | Core ports become `@runtime_checkable`. |
| ISP       | B+      | A-     | Keep narrow ports; move `ResearchStep` into a dedicated domain port. |
| DIP       | C       | B+     | Domain ports no longer import application modules; renderer is injected. |

## Pre-requisites
- Read `src/brief_scout/domain/ports/`, `src/brief_scout/application/services/`, and `tests/unit/test_intake_use_case.py`.
- Do **not** edit `src/brief_scout/main.py`, `src/brief_scout/infrastructure/`, or `src/brief_scout/interfaces/api/routes.py`; those are Agent 2 + integration territory.

## Tasks

### 1. Move `ResearchStep` into the domain layer
- Create `src/brief_scout/domain/ports/research_step_port.py` containing the `@runtime_checkable` `ResearchStep` Protocol (currently duplicated in `application/services/research_steps/__init__.py` and `application/services/research_pipeline.py`).
- Update `src/brief_scout/domain/ports/research_step_registry_port.py` to import `ResearchStep` from the new domain port instead of `application.services.research_steps`.
- Update `src/brief_scout/application/services/research_steps/__init__.py` to re-export `ResearchStep` from the domain port for backward compatibility, or update all internal imports directly.
- Update `src/brief_scout/application/services/research_pipeline.py` to import `ResearchStep` from the domain port and remove its local duplicate.

### 2. Move `PipelineEvent` into the domain layer
- Create `src/brief_scout/domain/ports/pipeline_event.py` containing the base `PipelineEvent` Pydantic model (stage, status, payload).
- Update `src/brief_scout/domain/ports/research_pipeline_port.py` to import `PipelineEvent` from the domain port.
- Update `src/brief_scout/domain/ports/pipeline_port.py` to import `PipelineEvent` from the domain port.
- Update `src/brief_scout/application/services/research_pipeline.py` to import the domain `PipelineEvent` and remove its local definition.
- Update `src/brief_scout/application/services/brief_generation_pipeline.py` to subclass/import the domain `PipelineEvent`.
- Update `src/brief_scout/interfaces/api/routes.py` imports (Agent 2 will wire renderer; you only fix imports here).

### 3. Remove `IntakeData.is_complete()` duplication
- Delete `is_complete()` from `src/brief_scout/domain/models/intake.py`.
- Update `src/brief_scout/application/services/brief_generation_pipeline.py`:
  - Add `completeness_checker: CompletenessChecker` to `__init__`.
  - Replace `session.intake_data.is_complete()` with `self._completeness_checker.check(session.intake_data).is_complete`.
- Update unit tests for the pipeline to provide a `CompletenessChecker`.

### 4. Consolidate template-renderer ownership
- Delete `src/brief_scout/application/services/template_renderer.py` and remove it from `src/brief_scout/application/services/__init__.py`.
- Update `src/brief_scout/application/services/journey_renderer.py`:
  - Make `renderer: TemplateRenderer` a required constructor argument (no fallback to a concrete Jinja2 class).
- Update `src/brief_scout/application/services/intake_prompt_builder.py`:
  - Make `renderer: TemplateRenderer` a required constructor argument.
- Update `src/brief_scout/application/services/journey_acknowledgement_service.py`:
  - It already accepts a renderer; verify it passes it to `JourneyRenderer`.
- Update unit tests that instantiate these builders/renderers to inject a small test double or the real infrastructure renderer.

### 5. Make core domain ports `@runtime_checkable`
- Add `@runtime_checkable` to:
  - `LLMPort` (`src/brief_scout/domain/ports/llm_port.py`)
  - `BriefStoragePort` (`src/brief_scout/domain/ports/storage_port.py`)
  - `TelemetryPort` (`src/brief_scout/domain/ports/telemetry_port.py`)
  - `ResearchTool` (`src/brief_scout/domain/ports/research_tool_port.py`)
  - `TemplateRenderer` (`src/brief_scout/domain/ports/application_ports.py`)

### 6. Application-layer test cleanup
- Rewrite `tests/unit/test_intake_use_case.py` to exercise the production `IntakeUseCase` (like `test_intake_use_case_source.py`) instead of the inline duplicate implementation.
- Update `tests/unit/test_prompt_builders_and_renderers.py` for required renderer injection.
- Rewrite `tests/integration/test_full_pipeline.py` to use the production `BriefGenerationPipeline` rather than the inline `FullPipeline` class.

## Files you will touch

### Create
- `src/brief_scout/domain/ports/research_step_port.py`
- `src/brief_scout/domain/ports/pipeline_event.py`

### Modify
- `src/brief_scout/domain/models/intake.py`
- `src/brief_scout/domain/ports/llm_port.py`
- `src/brief_scout/domain/ports/storage_port.py`
- `src/brief_scout/domain/ports/telemetry_port.py`
- `src/brief_scout/domain/ports/research_tool_port.py`
- `src/brief_scout/domain/ports/application_ports.py`
- `src/brief_scout/domain/ports/research_step_registry_port.py`
- `src/brief_scout/domain/ports/research_pipeline_port.py`
- `src/brief_scout/domain/ports/pipeline_port.py`
- `src/brief_scout/domain/ports/__init__.py`
- `src/brief_scout/application/services/research_pipeline.py`
- `src/brief_scout/application/services/brief_generation_pipeline.py`
- `src/brief_scout/application/services/research_steps/__init__.py`
- `src/brief_scout/application/services/journey_renderer.py`
- `src/brief_scout/application/services/intake_prompt_builder.py`
- `src/brief_scout/application/services/journey_acknowledgement_service.py`
- `src/brief_scout/application/services/__init__.py`
- `src/brief_scout/application/services/brief_markdown_renderer.py` (import only if needed)
- `src/brief_scout/interfaces/api/routes.py` (imports only)
- `tests/unit/test_intake_use_case.py`
- `tests/unit/test_prompt_builders_and_renderers.py`
- `tests/integration/test_full_pipeline.py`

### Delete
- `src/brief_scout/application/services/template_renderer.py`

## Acceptance criteria
- `uv run ruff check src tests` passes.
- `uv run ruff format --check src tests` passes.
- `uv run mypy src` passes.
- `uv run pytest tests/unit/test_intake_use_case.py tests/unit/test_prompt_builders_and_renderers.py tests/integration/test_full_pipeline.py tests/unit/test_category_classifier.py tests/unit/test_domain_models.py` passes.
- No file under `src/brief_scout/domain/ports/` imports from `src/brief_scout/application/`.
- `IntakeData` no longer has an `is_complete()` method.
- Only one `Jinja2TemplateRenderer` class remains in the codebase (the one in `src/brief_scout/infrastructure/template/`).
- Coverage for touched files does not drop below the current baseline.

## Notes / conflict avoidance
- Do **not** change `src/brief_scout/main.py` or `src/brief_scout/infrastructure/factories/`. The integration wave will wire the new `CompletenessChecker` dependency into `BriefGenerationPipeline` and update renderer wiring.
- If you need a new dependency in `main.py` to keep tests green, add it with a backward-compatible default and leave a `TODO(integration)` comment.
