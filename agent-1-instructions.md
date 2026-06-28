# Agent 1 Instructions — Domain & Application Layer Refactor

**Goal:** Address all Domain & Application layer SOLID concerns listed below, while staying inside your scope and honoring the cross-agent contracts so your branch can merge cleanly with Agent 2.

**Branch:** `refactor/agent-1-domain-application`  
**Worktree:** `../ai-onboarding-agent1` (create from original repo)  
**Base:** `development`

---

## Setup

Run these commands once from the original repository:

```bash
cd /Users/kennpalm/source/chase/ai-onboarding
git checkout development
git pull origin development
git branch refactor/agent-1-domain-application
git worktree add ../ai-onboarding-agent1 refactor/agent-1-domain-application
```

Then do **all** of your work inside `../ai-onboarding-agent1`:

```bash
cd /Users/kennpalm/source/chase/ai-onboarding-agent1
```

Commit frequently and push:

```bash
git push origin refactor/agent-1-domain-application
```

---

## Scope

### You MAY edit

- `src/brief_scout/application/use_cases/*.py`
- `src/brief_scout/application/services/*.py` (new files are expected)
- `src/brief_scout/domain/models/*.py`
- `src/brief_scout/domain/services/*.py`
- `src/brief_scout/application/dto/*.py`
- `src/brief_scout/domain/ports/application_ports.py` (local narrow protocols **only**)
- Corresponding unit tests under `tests/`
- `AGENTS.md` if your changes affect the playbook

### You MUST NOT edit

- `src/brief_scout/infrastructure/**/*`
- `src/brief_scout/interfaces/api/routes.py`
- `src/brief_scout/main.py`
- Official port files:
  - `src/brief_scout/domain/ports/telemetry_port.py`
  - `src/brief_scout/domain/ports/config_port.py`
  - `src/brief_scout/domain/ports/storage_port.py`
  - `src/brief_scout/domain/ports/llm_port.py`

If you need a narrower port than the official ones, define it locally in `src/brief_scout/domain/ports/application_ports.py`. The integration engineer will reconcile it with Agent 2’s official port redesign.

---

## Cross-Agent Contracts

Your code must expose the following contracts so Agent 2 and the integration engineer can consume it.

### 1. `BriefGenerationPipeline` (new application service)

Create `src/brief_scout/application/services/brief_generation_pipeline.py`.

```python
class PipelineEvent(BaseModel):
    stage: Literal["intake", "research", "synthesis", "complete"]
    status: Literal["started", "progress", "complete", "failed"]
    payload: dict[str, Any] = Field(default_factory=dict)

class BriefGenerationPipeline:
    def __init__(
        self,
        intake_use_case: IntakeUseCase,
        research_pipeline: ResearchPipeline,
        synthesis_use_case: SynthesisUseCase,
        storage: BriefStoragePort,  # keep existing port for now
    ) -> None: ...

    async def run(
        self,
        session: ChatSession,
        user_message: str,
    ) -> AsyncIterator[PipelineEvent]:
        """Yield progress events for intake, research, synthesis, and completion."""
```

- This removes the orchestration burden from `routes.py`.
- Do **not** emit SSE here; emit domain events only.

### 2. `ResearchPipeline` (new application service)

Create `src/brief_scout/application/services/research_pipeline.py`.

```python
class ResearchStep(Protocol):
    name: str
    async def execute(self, intake_data: IntakeData) -> BaseModel: ...

class ResearchPipeline:
    def __init__(self, steps: Sequence[ResearchStep], ...) -> None: ...
    async def execute(self, intake_data: IntakeData) -> ResearchBundle: ...
    async def stream(self, intake_data: IntakeData) -> AsyncIterator[PipelineEvent]: ...
```

- Replace the five hard-coded `_call_*` methods in `ResearchUseCase` with registered steps.
- `ResearchBundle` must be extensible (e.g., `results: dict[str, BaseModel]`).

### 3. `Status` Enum

Introduce in `src/brief_scout/domain/models/intake.py`:

```python
class Status(StrEnum):
    INTAKING = "intaking"
    RESEARCHING = "researching"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
```

Use it in `ChatSession`, DTOs, and use cases. Agent 2 will update `routes.py` to use it.

### 4. Public Use-Case Signatures

Keep these signatures stable:

- `IntakeUseCase.process_message(session, user_message) -> IntakeResponse`
- `SynthesisUseCase.execute(intake_data, research_bundle) -> Brief`
- `ResearchUseCase.execute(intake_data) -> ResearchBundle` (or deprecate in favor of `ResearchPipeline`)

### 5. No FakeLLM / Jinja2 Leaks

- Remove `demo_turn` logic from `IntakeUseCase`. Pass a generic `extraction_config` dict from provider extras straight through to the LLM port.
- Remove all Jinja2 imports from `IntakeJourney` and `IntakeUseCase`. Introduce a `TemplateRenderer` port/service abstraction.
- Remove direct infrastructure identifiers from `AppConfig` / `LLMProviderConfig` where possible (e.g., rename `adapter_class` to `adapter_id` and let Agent 2 map id → class).

---

## Assigned Concerns — 24 Items

### SRP

#### SRP-03 — `ResearchUseCase` mixes orchestration with prompt formatting, category inference, and error handling
- **File:** `src/brief_scout/application/use_cases/research_use_case.py`
- **Action:**
  - Extract keyword-based category inference into `src/brief_scout/domain/services/category_classifier.py`.
  - Extract prompt formatting into `src/brief_scout/application/services/research_prompt_builder.py` or use the dynamic `PromptsConfig` catalog.
  - Keep `ResearchUseCase` as a thin coordinator that delegates to `ResearchPipeline`, prompt builder, and classifier.

#### SRP-06 — `IntakeUseCase` combines conversation flow, prompt engineering, extraction config, and persistence
- **File:** `src/brief_scout/application/use_cases/intake_use_case.py`
- **Action:**
  - Extract extraction prompt building into `IntakePromptBuilder`.
  - Remove FakeLLM-specific `_select_extraction_config` (see DIP-01).
  - Keep only message handling, use-case delegation, and session persistence.

#### SRP-09 — `IntakeJourney` mixes schema definition, field-empty logic, template rendering, question routing, and completeness evaluation
- **File:** `src/brief_scout/domain/models/journey.py`
- **Action:**
  - Move Jinja2 template rendering out of `JourneyField`/`IntakeJourney`.
  - Keep schema, field metadata, emptiness rules, and routing inside the model.
  - Create `JourneyRenderer` service for question/acknowledgement/extraction-schema rendering.

#### SRP-10 — `Brief.to_markdown` puts presentation formatting inside a domain model
- **File:** `src/brief_scout/domain/models/brief.py`
- **Action:**
  - Move `to_markdown()` to `src/brief_scout/domain/services/brief_markdown_renderer.py` or an infrastructure renderer.
  - `Brief` remains a pure data model.

#### SRP-12 — `SynthesisUseCase` fuses orchestration, prompt building, and source attachment
- **File:** `src/brief_scout/application/use_cases/synthesis_use_case.py`
- **Action:**
  - Extract prompt building into `SynthesisPromptBuilder`.
  - Source attachment can move to a small domain service or stay in the use case, but not mixed with prompt string manipulation.

#### SRP-14 — `IntakeData` data model embeds completeness rules and scoring
- **File:** `src/brief_scout/domain/models/intake.py`
- **Action:**
  - Remove `is_complete` and `completion_score` properties from `IntakeData`.
  - Delegate completeness to `CompletenessChecker` / `IntakeJourney.is_complete`.
  - Update any callers (tests, DTOs).

#### SRP-15 — `CompletenessChecker` couples evaluation logic with telemetry emission
- **File:** `src/brief_scout/domain/services/completeness_checker.py`
- **Action:**
  - Remove telemetry logging from the checker.
  - If logging is still needed, inject a narrow `LoggerPort` defined in `application_ports.py`.
  - Return `CompletenessResult`; let callers log.

### OCP

#### OCP-01 — Research pipeline hard-codes the “5 research calls” (use-case side)
- **Files:** `src/brief_scout/application/use_cases/research_use_case.py`, `src/brief_scout/domain/models/research.py`
- **Action:**
  - Implement `ResearchPipeline` and `ResearchStep` registry.
  - Define each research step as a separate class in `src/brief_scout/application/services/research_steps/`.
  - Make `ResearchBundle` extensible (e.g., `results: dict[str, BaseModel]`).

#### OCP-02 — `ResearchBundle` is a closed aggregate of five concrete result types
- **File:** `src/brief_scout/domain/models/research.py`
- **Action:**
  - Replace the five typed fields with a generic `results: dict[str, BaseModel]` or a custom mapping.
  - Keep typed accessors as optional properties for backward compatibility if needed.

#### OCP-03 — `PromptsConfig` enumerates a fixed set of prompt templates
- **File:** `src/brief_scout/domain/models/config.py`
- **Action:**
  - Convert research prompts to `dict[str, PromptTemplateConfig]` (e.g., `research_steps: dict[str, PromptTemplateConfig]`).
  - Keep `synthesis` and `extraction_system` as named fields if still needed.
  - Ensure new prompts can be added in YAML without code changes.

#### OCP-08 — Category inference uses a closed keyword map
- **File:** `src/brief_scout/application/use_cases/research_use_case.py`
- **Action:**
  - Move `_infer_category` to `src/brief_scout/domain/services/category_classifier.py`.
  - Load keyword map from config or allow strategy injection.

#### OCP-09 — Journey field types are a closed literal
- **Files:** `src/brief_scout/domain/models/journey.py`, `src/brief_scout/domain/services/intake_data_merger.py`
- **Action:**
  - Introduce a `FieldTypeHandler` registry.
  - Register handlers for `string`, `list`, `object`, and future types (`number`, `boolean`, `date`).
  - Replace `if field.type == "..."` branches with registry lookups.

#### OCP-10 — Each research call has its own hard-coded prompt-formatting method
- **File:** `src/brief_scout/application/use_cases/research_use_case.py`
- **Action:**
  - Each `ResearchStep` reads its own prompt template from the dynamic catalog and formats it generically.
  - No step-specific methods on `ResearchUseCase`.

#### OCP-11 — Synthesis prompt placeholders are hard-coded
- **File:** `src/brief_scout/application/use_cases/synthesis_use_case.py`
- **Action:**
  - Use a template renderer with variable discovery, or pass serializable objects directly and let the template reference named variables (`{{intake_json}}`, `{{research_json}}`, etc.).
  - Avoid chained `.replace()` calls.

#### OCP-12 — Session status values are duplicated as string literals across layers (domain/DTO/use case side)
- **Files:** `src/brief_scout/domain/models/intake.py`, `src/brief_scout/application/dto/intake_dto.py`, `src/brief_scout/application/use_cases/intake_use_case.py`
- **Action:**
  - Introduce `Status` enum and replace all status strings in domain, DTOs, and use cases.
  - Agent 2 will update `routes.py`.

#### OCP-13 — `IntakeData` fields are fixed in code
- **File:** `src/brief_scout/domain/models/intake.py`
- **Action:**
  - Keep the explicit fields for the current schema, but make adding a field a single change (model attribute + journey schema entry).
  - Document the pattern in `AGENTS.md` and consider code-generation or a schema-driven base if feasible.

### LSP

#### LSP-09 — `ResearchUseCase` error-handling path diverges by adapter
- **File:** `src/brief_scout/application/use_cases/research_use_case.py`
- **Action:**
  - Decide on a single contract: either `complete_structured` always raises on failure, or the pipeline always catches and returns a default.
  - Document the contract and ensure `ResearchPipeline` handles errors consistently regardless of adapter.

#### LSP-10 — `IntakeUseCase` extraction error handling is adapter-dependent
- **File:** `src/brief_scout/application/use_cases/intake_use_case.py`
- **Action:**
  - On extraction failure, always preserve existing `session.intake_data`.
  - Do not depend on the Fake adapter returning a default empty model.

### ISP

#### ISP-10 — `CompletenessChecker` depends on the full `TelemetryPort` for one method
- **File:** `src/brief_scout/domain/services/completeness_checker.py`
- **Action:**
  - Change constructor to accept a narrow `LoggerPort` from `application_ports.py`.
  - Only call `logger.log(...)`.

#### ISP-11 — `IntakeUseCase` depends on the full `BriefStoragePort` only to save sessions
- **File:** `src/brief_scout/application/use_cases/intake_use_case.py`
- **Action:**
  - Change constructor to accept a narrow `SessionWriter` protocol from `application_ports.py`.

#### ISP-12 — `ResearchUseCase` and `SynthesisUseCase` depend on the full `LLMPort` only for structured completion
- **Files:** `src/brief_scout/application/use_cases/research_use_case.py`, `src/brief_scout/application/use_cases/synthesis_use_case.py`
- **Action:**
  - Change constructors to accept a narrow `StructuredCompletionPort` protocol from `application_ports.py`.

### DIP

#### DIP-01 — `IntakeUseCase` builds FakeLLM-specific `demo_turn` config
- **File:** `src/brief_scout/application/use_cases/intake_use_case.py`
- **Action:**
  - Delete `_select_extraction_config`.
  - Pass `provider_config.extras` (or similar generic config dict) as the `config` argument to `complete_structured`.
  - Do not reference FakeLLM specifics.

#### DIP-08 — Domain model `IntakeJourney` depends on Jinja2
- **File:** `src/brief_scout/domain/models/journey.py`
- **Action:**
  - Remove `from jinja2 import Template`.
  - Move rendering to a `JourneyRenderer` service or a `TemplateRenderer` port.

#### DIP-09 — `IntakeUseCase` depends on Jinja2
- **File:** `src/brief_scout/application/use_cases/intake_use_case.py`
- **Action:**
  - Remove `from jinja2 import Template`.
  - Use the `TemplateRenderer` port/service.

#### DIP-10 — Domain config models encode concrete infrastructure names/class paths
- **File:** `src/brief_scout/domain/models/config.py`
- **Action:**
  - Rename `LLMProviderConfig.adapter_class` to `adapter_id` (a generic identifier string).
  - Treat `storage_adapter` and `telemetry.adapter` as generic adapter identifiers, not concrete class names.
  - Agent 2 will map these identifiers to implementations via a registry.

---

## Suggested New Files

```
src/brief_scout/application/services/
  brief_generation_pipeline.py
  research_pipeline.py
  research_prompt_builder.py
  synthesis_prompt_builder.py
  intake_prompt_builder.py
  journey_renderer.py
  brief_markdown_renderer.py

src/brief_scout/application/services/research_steps/
  brand_audit_step.py
  competitor_scan_step.py
  trend_pulse_step.py
  customer_voice_step.py
  hook_mining_step.py

src/brief_scout/domain/services/
  category_classifier.py

src/brief_scout/domain/ports/
  application_ports.py
```

---

## Quality Gates

Before declaring done, run in your worktree:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/brief_scout
uv run pytest --cov=src/brief_scout --cov-report=term-missing
```

- All linting and type-checking must pass.
- Test coverage must remain ≥ 93%.
- If a test fails because it depends on Agent 2 changes, mark it as expected-integration-failure in a commit message and move on. Do not break the test suite silently.

---

## Deliverables

1. All 24 assigned concerns addressed in code.
2. New application services and domain services created as needed.
3. Stable public signatures for use cases and pipeline.
4. Clean separation: no infrastructure imports in `application` or `domain`.
5. Passing quality gates in your branch.
6. Branch `refactor/agent-1-domain-application` pushed to origin.

---

*Do not modify Agent 2 files. When in doubt, define a local protocol in `application_ports.py` and let the integration engineer reconcile it.*
