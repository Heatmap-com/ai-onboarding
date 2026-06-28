# Integration Plan — Parallel SOLID Refactor

This document coordinates a parallel refactor that addresses all 75 SOLID concerns identified in `SOLID_CONFORMANCE_ANALYSIS.md`.

- **Agent 1** owns the **Domain & Application** layer.
- **Agent 2** owns the **Infrastructure & Interface** layer (ports, adapters, routes, composition root).
- **Integration Engineer** merges both branches, resolves boundary conflicts, and verifies all quality gates.

Each agent works in a **separate git worktree** on a **separate refactor branch** so they cannot accidentally step on each other’s files.

---

## Branch & Worktree Layout

| Role | Branch | Suggested Worktree |
|---|---|---|
| Agent 1 | `refactor/agent-1-domain-application` | `../ai-onboarding-agent1` |
| Agent 2 | `refactor/agent-2-infrastructure-interface` | `../ai-onboarding-agent2` |
| Integration | `refactor/integration-merge` | `../ai-onboarding-integration` |

### Creating the Branches (run once from the original repo)

```bash
cd /Users/kennpalm/source/chase/ai-onboarding
git checkout development
git pull origin development

# Agent 1
git branch refactor/agent-1-domain-application
git worktree add ../ai-onboarding-agent1 refactor/agent-1-domain-application

# Agent 2
git branch refactor/agent-2-infrastructure-interface
git worktree add ../ai-onboarding-agent2 refactor/agent-2-infrastructure-interface

# Integration
git branch refactor/integration-merge
git worktree add ../ai-onboarding-integration refactor/integration-merge
```

> **Important:** Agents must commit and push their branches frequently. The integration engineer must not rewrite agent branch history.

---

## Scope Boundaries

### Agent 1 — Domain & Application Layer

**May edit:**
- `src/brief_scout/application/use_cases/*.py`
- `src/brief_scout/application/services/*.py` (new orchestration services)
- `src/brief_scout/domain/models/*.py`
- `src/brief_scout/domain/services/*.py`
- `src/brief_scout/application/dto/*.py`
- `src/brief_scout/domain/ports/application_ports.py` (local narrow protocols **only**)
- Corresponding tests and `AGENTS.md` updates.

**Must NOT edit:**
- `src/brief_scout/infrastructure/**/*`
- `src/brief_scout/interfaces/api/routes.py`
- `src/brief_scout/main.py`
- Official port files: `src/brief_scout/domain/ports/telemetry_port.py`, `config_port.py`, `storage_port.py`, `llm_port.py`.

### Agent 2 — Infrastructure & Interface Layer

**May edit:**
- `src/brief_scout/domain/ports/*.py` (official port redesign)
- `src/brief_scout/infrastructure/**/*.py`
- `src/brief_scout/interfaces/api/routes.py`
- `src/brief_scout/main.py`
- Corresponding tests and `AGENTS.md` updates.

**Must NOT edit:**
- `src/brief_scout/application/use_cases/*.py`
- `src/brief_scout/application/services/*.py` (created by Agent 1)
- `src/brief_scout/domain/models/*.py`
- `src/brief_scout/domain/services/*.py`
- `src/brief_scout/application/dto/*.py`
- Agent 1’s `src/brief_scout/domain/ports/application_ports.py`.

---

## Cross-Agent Contracts

The following contracts must be honored so the branches can merge cleanly.

### 1. Pipeline Orchestration Service

Agent 1 creates a new application service, e.g.:

```python
# src/brief_scout/application/services/brief_generation_pipeline.py
class BriefGenerationPipeline:
    async def run(self, session: ChatSession, user_message: str) -> AsyncIterator[PipelineEvent]:
        ...
```

- `PipelineEvent` is a small Pydantic model with `stage`, `status`, `payload`.
- The pipeline performs intake → research → synthesis → brief persistence.
- It yields progress events instead of directly emitting SSE.

Agent 2 updates `routes.py` to instantiate/inject the pipeline and wrap each `PipelineEvent` in `_make_event(...)` / SSE.

### 2. Research Step Registry

Agent 1 creates a research step registry / strategy collection:

```python
# src/brief_scout/application/services/research_pipeline.py
class ResearchPipeline:
    def __init__(self, steps: dict[str, ResearchStep], ...) -> None: ...
    async def execute(self, intake_data: IntakeData) -> ResearchBundle: ...
```

Agent 2 does **not** call private `ResearchUseCase._call_*` methods from `routes.py`. It calls the public pipeline API.

### 3. Status Enum

Agent 1 introduces a `Status` enum in the domain:

```python
# src/brief_scout/domain/models/intake.py
from enum import StrEnum
class Status(StrEnum):
    INTAKING = "intaking"
    RESEARCHING = "researching"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
```

Agent 2 updates `routes.py` to use `Status` values where applicable.

### 4. Narrow Ports

Agent 2 designs new narrow ports (e.g., `LoggerPort`, `SessionStoragePort`, `StructuredCompletionPort`).
The integration engineer updates Agent 1’s local protocols / consumer type hints to point to Agent 2’s official ports.

### 5. Prompt & Template Rendering

Agent 1 removes Jinja2 from `IntakeJourney` and `IntakeUseCase` by introducing a `TemplateRenderer` port or service.
Agent 2 provides a Jinja2-based adapter for that renderer and wires it in `main.py`.

### 6. Demo / FakeLLM Configuration

Agent 1 removes `demo_turn` logic from `IntakeUseCase`. It may pass a generic `extraction_config` dict (from provider extras) through to the LLM port.
Agent 2 makes `FakeLLMAdapter` consume that generic config without leaking FakeLLM specifics into the application layer.

---

## Concern Ownership Matrix

| ID | Concern | Primary Owner | Notes |
|---|---|---|---|
| SRP-01 | `stream_message` route handler orchestrates the whole pipeline | **Joint** | Agent 1 extracts pipeline service; Agent 2 thins the route. |
| SRP-02 | `FakeLLMAdapter` is a fixture loader, matcher, demo player, latency simulator, logger, and parser | Agent 2 | |
| SRP-03 | `ResearchUseCase` mixes orchestration with prompt formatting, category inference, and error handling | Agent 1 | |
| SRP-04 | `create_app` factory couples composition-root wiring with concrete adapter selection and env parsing | Agent 2 | |
| SRP-05 | `YAMLConfigAdapter` loads files, deep-merges, interpolates env vars, validates, caches, and reloads | Agent 2 | |
| SRP-06 | `IntakeUseCase` combines conversation flow, prompt engineering, extraction config, and persistence | Agent 1 | |
| SRP-07 | Real LLM adapters each mix SDK client creation, request formatting, response mapping, error classification, and JSON-mode plumbing | Agent 2 | |
| SRP-08 | `LocalFileTelemetryAdapter` combines logging, event recording, tracing spans, correlation-ID context, and file I/O | Agent 2 | |
| SRP-09 | `IntakeJourney` mixes schema definition, field-empty logic, template rendering, question routing, and completeness evaluation | Agent 1 | |
| SRP-10 | `Brief.to_markdown` puts presentation formatting inside a domain model | Agent 1 | |
| SRP-11 | `_create_llm_adapter` mixes dynamic importing with FakeLLM special-casing | Agent 2 | |
| SRP-12 | `SynthesisUseCase` fuses orchestration, prompt building, and source attachment | Agent 1 | |
| SRP-13 | `routes.py` module overall is a kitchen-sink interface layer | **Joint** | Agent 1 extracts orchestration; Agent 2 keeps HTTP/SSE/DTO thin. |
| SRP-14 | `IntakeData` data model embeds completeness rules and scoring | Agent 1 | |
| SRP-15 | `CompletenessChecker` couples evaluation logic with telemetry emission | Agent 1 | |
| OCP-01 | Research pipeline hard-codes the “5 research calls” | **Joint** | Agent 1 builds pluggable pipeline; Agent 2 consumes public API in route. |
| OCP-02 | `ResearchBundle` is a closed aggregate of five concrete result types | Agent 1 | |
| OCP-03 | `PromptsConfig` enumerates a fixed set of prompt templates | Agent 1 | |
| OCP-04 | Storage adapter selection is a hard-coded `if/else` | Agent 2 | |
| OCP-05 | Telemetry adapter is instantiated as a concrete `LocalFileTelemetryAdapter` | Agent 2 | |
| OCP-06 | LLM factory special-cases `FakeLLMAdapter` and uses a fixed constructor signature | Agent 2 | |
| OCP-07 | SSE stream route re-implements the research step orchestration | **Joint** | Agent 1 emits domain pipeline events; Agent 2 wraps in SSE. |
| OCP-08 | Category inference uses a closed keyword map | Agent 1 | |
| OCP-09 | Journey field types are a closed literal | Agent 1 | |
| OCP-10 | Each research call has its own hard-coded prompt-formatting method | Agent 1 | |
| OCP-11 | Synthesis prompt placeholders are hard-coded | Agent 1 | |
| OCP-12 | Session status values are duplicated as string literals across layers | **Joint** | Agent 1 introduces `Status` enum; Agent 2 uses it in routes. |
| OCP-13 | `IntakeData` fields are fixed in code | Agent 1 | |
| OCP-14 | `YAMLConfigAdapter` hard-codes file names and YAML source | Agent 2 | |
| OCP-15 | `JourneyLoader` hard-codes file names and YAML format | Agent 2 | |
| LSP-01 | `FakeLLMAdapter.complete_structured` weakens the failure post-condition | Agent 2 | |
| LSP-02 | `FileSystemStorageAdapter.get_session` raises on corrupted files | Agent 2 | |
| LSP-03 | `YAMLConfigAdapter.get_prompt_template` silently degrades string-valued templates | Agent 2 | |
| LSP-04 | `ClaudeAdapter` silently drops system-role context items | Agent 2 | |
| LSP-05 | `TelemetryPort.log` accepts `str` without a normalization contract | Agent 2 | |
| LSP-06 | `LocalFileTelemetryAdapter.start_span` mutates correlation ID | Agent 2 | |
| LSP-07 | LLM adapters do not explicitly declare `LLMPort` implementation | Agent 2 | |
| LSP-08 | `LocalFileTelemetryAdapter.end_span` swallows unknown span IDs | Agent 2 | |
| LSP-09 | `ResearchUseCase` error-handling path diverges by adapter | Agent 1 | |
| LSP-10 | `IntakeUseCase` extraction error handling is adapter-dependent | Agent 1 | |
| LSP-11 | `FileSystemStorageAdapter.list_sessions` silently skips corrupted files | Agent 2 | |
| LSP-12 | `FakeLLMAdapter.complete` serializes dict responses as JSON strings | Agent 2 | |
| LSP-13 | `LLMResponse.metadata` shape differs across adapters | Agent 2 | |
| LSP-14 | `LangChainBaseAdapter._handle_error` depends on an abstract property | Agent 2 | |
| LSP-15 | `ConfigurationPort.reload()` contract is under-specified | Agent 2 | |
| ISP-01 | `TelemetryPort` bundles logging, events, tracing, and correlation context | Agent 2 | |
| ISP-02 | `ConfigurationPort` mixes app config, provider lookup, prompt lookup, and reload | Agent 2 | |
| ISP-03 | `BriefStoragePort` merges session and brief persistence | Agent 2 | |
| ISP-04 | `LLMPort` combines generic and structured completion | Agent 2 | |
| ISP-05 | `ConfigurationPort.app_config` exposes the entire `AppConfig` aggregate | Agent 2 | |
| ISP-06 | `BriefStoragePort.list_sessions` is unused interface baggage | Agent 2 | |
| ISP-07 | `ConfigurationPort.reload` is unused mutability on a read interface | Agent 2 | |
| ISP-08 | `ConfigurationPort.get_prompt_template` is unused | Agent 2 | |
| ISP-09 | `LLMPort.complete` is unused by application clients | Agent 2 | |
| ISP-10 | `CompletenessChecker` depends on the full `TelemetryPort` for one method | Agent 1 | |
| ISP-11 | `IntakeUseCase` depends on the full `BriefStoragePort` only to save sessions | Agent 1 | |
| ISP-12 | `ResearchUseCase` and `SynthesisUseCase` depend on the full `LLMPort` only for structured completion | Agent 1 | |
| ISP-13 | `FakeLLMAdapter` exposes test-only methods outside the `LLMPort` contract | Agent 2 | |
| ISP-14 | `FakeLLMAdapter` accepts the full `TelemetryPort` but uses only logging and event recording | Agent 2 | |
| ISP-15 | `LangChainBaseAdapter` is a fat class-level interface with methods beyond `LLMPort` | Agent 2 | |
| DIP-01 | `IntakeUseCase` builds FakeLLM-specific `demo_turn` config | Agent 1 | |
| DIP-02 | `main._create_llm_adapter` special-cases `FakeLLMAdapter` construction | Agent 2 | |
| DIP-03 | `LLMPort` uses an untyped `dict[str, Any]` config bag | Agent 2 | |
| DIP-04 | Composition root directly instantiates `YAMLConfigAdapter` | Agent 2 | |
| DIP-05 | Composition root directly instantiates `LocalFileTelemetryAdapter` | Agent 2 | |
| DIP-06 | Storage adapter selection hard-codes concrete classes | Agent 2 | |
| DIP-07 | Composition root directly instantiates `JourneyLoader` | Agent 2 | |
| DIP-08 | Domain model `IntakeJourney` depends on Jinja2 | Agent 1 | |
| DIP-09 | `IntakeUseCase` depends on Jinja2 | Agent 1 | |
| DIP-10 | Domain config models encode concrete infrastructure names/class paths | Agent 1 | |
| DIP-11 | `routes.py` calls private methods on `ResearchUseCase` | **Joint** | Agent 1 exposes public pipeline; Agent 2 uses it. |
| DIP-12 | Routes use a service-locator pattern via `request.app.state` | Agent 2 | |
| DIP-13 | `FakeLLMAdapter` exposes non-port methods | Agent 2 | |
| DIP-14 | Real LLM adapters ignore `LangChainBaseAdapter` and duplicate logic | Agent 2 | |
| DIP-15 | Composition root hard-codes runtime paths and defaults | Agent 2 | |

---

## Integration Workflow

1. **Wait for both agents to push their branches** and confirm their own unit tests pass.
2. In the integration worktree:
   ```bash
   cd /Users/kennpalm/source/chase/ai-onboarding-integration
   git checkout refactor/integration-merge
   git merge refactor/agent-1-domain-application --no-ff -m "Merge agent 1 domain/application refactor"
   git merge refactor/agent-2-infrastructure-interface --no-ff -m "Merge agent 2 infrastructure/interface refactor"
   ```
3. **Resolve conflicts** in the hot spots listed below.
4. **Reconcile local protocols:** Replace Agent 1’s `domain/ports/application_ports.py` references with Agent 2’s official narrow ports wherever possible.
5. **Wire new pipeline service** in `routes.py` and `main.py`.
6. **Run quality gates** (see below).
7. **Run the demo** to ensure the end-to-end onboarding flow still produces `demo_conversation.md`.
8. **Update `AGENTS.md`** and any architecture notes.
9. **Push** the integration branch and open a PR/merge to `development`.

### Conflict Hot Spots

- `src/brief_scout/interfaces/api/routes.py` — Agent 2 changes route signatures; Agent 1 introduces new pipeline service.
- `src/brief_scout/main.py` — Agent 2 changes wiring; Agent 1 may add new services to wire.
- `src/brief_scout/domain/ports/*.py` — Agent 2 redesigns; Agent 1 may have added local protocols.
- `src/brief_scout/domain/models/config.py` — Agent 1 changes config schema; Agent 2’s adapters consume it.
- `src/brief_scout/application/use_cases/research_use_case.py` — Agent 1 changes public surface; Agent 2 expects public pipeline.

---

## Acceptance Criteria

- [ ] All 75 concerns in `SOLID_CONFORMANCE_ANALYSIS.md` have a corresponding change or explicit design decision documented in `integration.md`.
- [ ] `ruff check .` and `ruff format --check .` pass.
- [ ] `mypy src/brief_scout` passes (strict).
- [ ] `pytest` passes with ≥ 93% coverage.
- [ ] Demo runs end-to-end and `demo_conversation.md` is generated successfully.
- [ ] `AGENTS.md` is updated with new extension points (ports, registries, pipeline).
- [ ] No direct infrastructure imports remain in `application` or `domain` layers.
- [ ] Routes layer is thin: no business orchestration, no private-method calls, no direct storage access except through injected ports.

---

*This plan assumes the starting point is the `development` branch as of the SOLID analysis.*
