# Agent 2 Instructions — Infrastructure & Interface Layer Refactor

**Goal:** Address all Infrastructure & Interface layer SOLID concerns listed below, while staying inside your scope and honoring the cross-agent contracts so your branch can merge cleanly with Agent 1.

**Branch:** `refactor/agent-2-infrastructure-interface`  
**Worktree:** `../ai-onboarding-agent2` (create from original repo)  
**Base:** `development`

---

## Setup

Run these commands once from the original repository:

```bash
cd /Users/kennpalm/source/chase/ai-onboarding
git checkout development
git pull origin development
git branch refactor/agent-2-infrastructure-interface
git worktree add ../ai-onboarding-agent2 refactor/agent-2-infrastructure-interface
```

Then do **all** of your work inside `../ai-onboarding-agent2`:

```bash
cd /Users/kennpalm/source/chase/ai-onboarding-agent2
```

Commit frequently and push:

```bash
git push origin refactor/agent-2-infrastructure-interface
```

---

## Scope

### You MAY edit

- `src/brief_scout/domain/ports/*.py` (official port redesign)
- `src/brief_scout/infrastructure/**/*.py`
- `src/brief_scout/interfaces/api/routes.py`
- `src/brief_scout/main.py`
- Corresponding unit/integration tests under `tests/`
- `AGENTS.md` if your changes affect the playbook

### You MUST NOT edit

- `src/brief_scout/application/use_cases/*.py`
- `src/brief_scout/application/services/*.py` (created by Agent 1)
- `src/brief_scout/domain/models/*.py`
- `src/brief_scout/domain/services/*.py`
- `src/brief_scout/application/dto/*.py`
- `src/brief_scout/domain/ports/application_ports.py` (Agent 1’s local protocols)

You may **read** those files to understand the contracts, but do not modify them.

---

## Cross-Agent Contracts

Your code must consume the following contracts from Agent 1.

### 1. `BriefGenerationPipeline`

Agent 1 creates `src/brief_scout/application/services/brief_generation_pipeline.py`.

Your job:
- In `main.py`, construct `BriefGenerationPipeline` from `IntakeUseCase`, `ResearchPipeline`, `SynthesisUseCase`, and storage.
- In `routes.py`, replace the inline pipeline orchestration in `stream_message` with a call to `pipeline.run(session, user_message)`.
- Convert each `PipelineEvent` to an SSE event via `_make_event`.

### 2. `ResearchPipeline`

Agent 1 creates `src/brief_scout/application/services/research_pipeline.py` with a public `execute` and/or `stream` method.

Your job:
- Do **not** call private `ResearchUseCase._call_*` methods from `routes.py`.
- Use the public pipeline API.

### 3. `Status` Enum

Agent 1 introduces `Status` in `src/brief_scout/domain/models/intake.py`.

Your job:
- Update `routes.py` to use `Status` values instead of string literals.

### 4. Narrow Ports

You redesign the official ports. The integration engineer will update Agent 1’s consumers to use them. You may keep the old fat ports as deprecated aliases or composite protocols for backward compatibility during the merge.

### 5. Adapter Identifiers

Agent 1 changes `LLMProviderConfig.adapter_class` to `adapter_id` and treats `storage_adapter` / `telemetry.adapter` as generic identifiers.

Your job:
- Build adapter registries in `main.py` (or `infrastructure/factories/`) that map `adapter_id` → constructor.

### 6. `TemplateRenderer`

Agent 1 removes Jinja2 from domain/application models and expects a `TemplateRenderer` port/service.

Your job:
- Provide a Jinja2-based `TemplateRenderer` adapter and wire it in `main.py`.

---

## Assigned Concerns — 51 Items

### SRP

#### SRP-01 — `stream_message` route handler orchestrates the whole pipeline
- **File:** `src/brief_scout/interfaces/api/routes.py:126-296`
- **Action:**
  - Remove all intake/research/synthesis orchestration from `stream_message`.
  - Delegate to `BriefGenerationPipeline` from Agent 1.
  - The route should only parse params, load the session, run the pipeline, and yield SSE events.

#### SRP-02 — `FakeLLMAdapter` is a fixture loader, matcher, demo player, latency simulator, logger, and parser
- **File:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:44-443`
- **Action:**
  - Split into focused collaborators:
    - `FixtureRepository` — recursive loading and keyword indexing.
    - `DemoJourneyPlayer` — demo-journey YAML turn synthesis.
    - `FixtureMatcher` — prompt-to-fixture matching strategies.
    - Keep `FakeLLMAdapter` as a thin coordinator.
  - Remove test-only methods from the public surface (see ISP-13).

#### SRP-04 — `create_app` factory couples composition-root wiring with concrete adapter selection and env parsing
- **File:** `src/brief_scout/main.py:39-203`
- **Action:**
  - Move adapter resolution and instantiation to dedicated factory modules (`infrastructure/factories/`).
  - `create_app` should only load config, call factories, wire use cases/services, and build FastAPI.

#### SRP-05 — `YAMLConfigAdapter` loads files, deep-merges, interpolates env vars, validates, caches, and reloads
- **File:** `src/brief_scout/infrastructure/config/yaml_config_adapter.py:38-258`
- **Action:**
  - Split responsibilities:
    - `YamlLoader` — file I/O.
    - `ConfigMerger` — default + env deep merge.
    - `EnvInterpolator` — `${VAR}` substitution.
    - `YAMLConfigAdapter` coordinates caching/validation.

#### SRP-07 — Real LLM adapters each mix SDK client creation, request formatting, response mapping, error classification, and JSON-mode plumbing
- **Files:** `src/brief_scout/infrastructure/llm/openai_adapter.py:23-269`, `kimi_adapter.py:28-277`, `claude_adapter.py:23-253`
- **Action:**
  - Extract common behavior into shared helpers or a real base class (see DIP-14).
  - Each adapter should only configure provider-specific client/message details.

#### SRP-08 — `LocalFileTelemetryAdapter` combines logging, event recording, tracing spans, correlation-ID context, and file I/O
- **File:** `src/brief_scout/infrastructure/telemetry/local_file_adapter.py:43-246`
- **Action:**
  - Split into smaller classes:
    - `JsonlWriter` — daily JSONL file I/O.
    - `SpanStore` — in-memory span tracking.
    - `LocalFileTelemetryAdapter` implements the narrow ports by composing these.

#### SRP-11 — `_create_llm_adapter` mixes dynamic importing with FakeLLM special-casing
- **File:** `src/brief_scout/main.py:206-255`
- **Action:**
  - Replace with a generic `LLMAdapterFactory` that looks up `adapter_id` in a registry.
  - No special branch for FakeLLM; register it like any other adapter.

#### SRP-13 — `routes.py` module overall is a kitchen-sink interface layer
- **File:** `src/brief_scout/interfaces/api/routes.py:1-400`
- **Action:**
  - Remove pipeline orchestration and dead code (`_dict_to_intake_data`).
  - Keep route definitions, thin validation, DTO mapping, and SSE formatting.
  - Move any remaining business logic into injected services.

### OCP

#### OCP-01 — Research pipeline hard-codes the “5 research calls” (route side)
- **File:** `src/brief_scout/interfaces/api/routes.py:189-261`
- **Action:**
  - Delete the inline `research_calls`, `default_map`, and positional `ResearchBundle` construction.
  - Use `BriefGenerationPipeline` / `ResearchPipeline` from Agent 1.

#### OCP-04 — Storage adapter selection is a hard-coded `if/else`
- **File:** `src/brief_scout/main.py:95-109`
- **Action:**
  - Introduce a `StorageAdapterFactory` / registry keyed by `adapter_id`.
  - Remove the inline `if/else`.

#### OCP-05 — Telemetry adapter is instantiated as a concrete `LocalFileTelemetryAdapter`
- **File:** `src/brief_scout/main.py:78-93`
- **Action:**
  - Use the telemetry `adapter_id` from config to select an implementation via a registry/factory.
  - Do not hard-code `LocalFileTelemetryAdapter` instantiation.

#### OCP-06 — LLM factory special-cases `FakeLLMAdapter` and uses a fixed constructor signature
- **File:** `src/brief_scout/main.py:206-255`
- **Action:**
  - Register each LLM adapter with its accepted config schema in a registry.
  - Construct generically from the registry.

#### OCP-07 — SSE stream route re-implements the research step orchestration
- **File:** `src/brief_scout/interfaces/api/routes.py:189-261`
- **Action:**
  - Consume `ResearchPipeline.stream()` / `BriefGenerationPipeline.run()` events.
  - Do not rebuild step lists or defaults in the route.

#### OCP-12 — Session status values are duplicated as string literals across layers (route side)
- **File:** `src/brief_scout/interfaces/api/routes.py:270`
- **Action:**
  - Import and use `Status` enum from Agent 1.

#### OCP-14 — `YAMLConfigAdapter` hard-codes file names and YAML source
- **File:** `src/brief_scout/infrastructure/config/yaml_config_adapter.py:150-194`
- **Action:**
  - Inject source paths or a `ConfigSource` abstraction.
  - Support different file naming conventions or remote sources without adapter changes.

#### OCP-15 — `JourneyLoader` hard-codes file names and YAML format
- **File:** `src/brief_scout/infrastructure/config/journey_loader.py:39-70`
- **Action:**
  - Introduce a `JourneySource` port.
  - Provide a `YamlFileJourneySource` implementation; allow future DB/CMS sources.

### LSP

#### LSP-01 — `FakeLLMAdapter.complete_structured` weakens the failure post-condition
- **File:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:337-400`
- **Action:**
  - Align with real adapters: raise `LLMCallError` on JSON/validation failures.
  - Do not silently return a default instance.

#### LSP-02 — `FileSystemStorageAdapter.get_session` raises on corrupted files
- **File:** `src/brief_scout/infrastructure/storage/file_system_adapter.py:65-77`
- **Action:**
  - Catch `ValidationError` and return `None` to honor the `ChatSession | None` contract.
  - Log the corruption event.

#### LSP-03 — `YAMLConfigAdapter.get_prompt_template` silently degrades string-valued templates
- **File:** `src/brief_scout/infrastructure/config/yaml_config_adapter.py:109-137`
- **Action:**
  - For string-valued templates, wrap the string into `PromptTemplateConfig(system=..., user=template_string)` or raise a clear config error if ambiguous.
  - Never return an empty config that discards data.

#### LSP-04 — `ClaudeAdapter` silently drops system-role context items
- **File:** `src/brief_scout/infrastructure/llm/claude_adapter.py:205-218`
- **Action:**
  - Preserve system context by mapping it to the Anthropic `system` parameter or by combining it visibly into user messages.
  - Document the behavior; do not silently drop.

#### LSP-05 — `TelemetryPort.log` accepts `str` without a normalization contract
- **Files:** `src/brief_scout/domain/ports/telemetry_port.py:55-60`, `src/brief_scout/infrastructure/telemetry/local_file_adapter.py:81-107`
- **Action:**
  - Tighten the port to accept only `LogLevel`.
  - Remove string normalization from `LocalFileTelemetryAdapter`.

#### LSP-06 — `LocalFileTelemetryAdapter.start_span` mutates correlation ID
- **File:** `src/brief_scout/infrastructure/telemetry/local_file_adapter.py:134-177`
- **Action:**
  - Remove the side effect from `start_span`.
  - Keep correlation-ID management explicit via `get/set_correlation_id`.

#### LSP-07 — LLM adapters do not explicitly declare `LLMPort` implementation
- **Files:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:44`, `openai_adapter.py:23`, `claude_adapter.py:23`, `kimi_adapter.py:28`, `langchain_base.py:27`
- **Action:**
  - Make protocols `@runtime_checkable` OR have adapters explicitly inherit from the new narrow ports (e.g., `class OpenAIAdapter(StructuredCompletionPort, CompletionPort)`).

#### LSP-08 — `LocalFileTelemetryAdapter.end_span` swallows unknown span IDs
- **File:** `src/brief_scout/infrastructure/telemetry/local_file_adapter.py:179-207`
- **Action:**
  - Document the contract on the port: either raise `KeyError` for unknown IDs or always return.
  - Pick one behavior and apply it consistently.

#### LSP-11 — `FileSystemStorageAdapter.list_sessions` silently skips corrupted files
- **File:** `src/brief_scout/infrastructure/storage/file_system_adapter.py:103-128`
- **Action:**
  - Do not use bare `except Exception`.
  - Log and surface corrupted files (e.g., return a result object with sessions + errors, or raise a dedicated exception).

#### LSP-12 — `FakeLLMAdapter.complete` serializes dict responses as JSON strings
- **File:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:251-335`
- **Action:**
  - Keep fixture `response` as a string in fixtures, or if it is a dict, do not stringify it for the generic `complete()` path.
  - Ensure `LLMResponse.content` is plain text.

#### LSP-13 — `LLMResponse.metadata` shape differs across adapters
- **Files:** `fake_llm_adapter.py:305-308`, `openai_adapter.py:113-118`, `claude_adapter.py:129-132`, `kimi_adapter.py:121-127`
- **Action:**
  - Define a common set of keys (e.g., `provider`, `model`, `tokens_used`, `latency_ms`).
  - Put provider-specific extras under a `provider_metadata` sub-key.

#### LSP-14 — `LangChainBaseAdapter._handle_error` depends on an abstract property
- **File:** `src/brief_scout/infrastructure/llm/langchain_base.py:132-153`
- **Action:**
  - Provide a concrete default for `provider_name` or refactor `_handle_error` so it does not require the abstract property.
  - Alternatively, make `_handle_error` abstract.

#### LSP-15 — `ConfigurationPort.reload()` contract is under-specified
- **Files:** `src/brief_scout/domain/ports/config_port.py:60-66`, `src/brief_scout/infrastructure/config/yaml_config_adapter.py:139-148`
- **Action:**
  - Document on the port whether `reload()` is eager or lazy and what exceptions may propagate.
  - Make the YAML adapter behavior match the documented contract.

### ISP

#### ISP-01 — `TelemetryPort` bundles logging, events, tracing, and correlation context
- **File:** `src/brief_scout/domain/ports/telemetry_port.py:48-119`
- **Action:**
  - Split into:
    - `LoggerPort`
    - `EventRecorder`
    - `SpanContext` (start/end span)
    - `CorrelationContext` (get/set correlation id)
  - `TelemetryPort` may remain a convenience composite protocol for composition-root wiring only.

#### ISP-02 — `ConfigurationPort` mixes app config, provider lookup, prompt lookup, and reload
- **File:** `src/brief_scout/domain/ports/config_port.py:16-66`
- **Action:**
  - Split into:
    - `AppConfigProvider`
    - `ProviderConfigSource`
    - `PromptTemplateProvider`
    - `ReloadableConfig` (or remove `reload()` if unused)

#### ISP-03 — `BriefStoragePort` merges session and brief persistence
- **File:** `src/brief_scout/domain/ports/storage_port.py:18-74`
- **Action:**
  - Split into `SessionStoragePort` and `BriefStoragePort`.
  - Update adapters to implement both if they provide both.

#### ISP-04 — `LLMPort` combines generic and structured completion
- **File:** `src/brief_scout/domain/ports/llm_port.py:53-104`
- **Action:**
  - Create `StructuredCompletionPort` for use cases.
  - Create `CompletionPort` for generic text completion.
  - `LLMPort` can extend both for full adapters.

#### ISP-05 — `ConfigurationPort.app_config` exposes the entire `AppConfig` aggregate
- **Files:** `src/brief_scout/domain/ports/config_port.py:23-30`, `src/brief_scout/domain/models/config.py:56-75`
- **Action:**
  - Provide narrow read-only views (`PromptsProvider`, `AppMetadataProvider`).
  - Keep `AppConfigProvider` for composition root only.

#### ISP-06 — `BriefStoragePort.list_sessions` is unused interface baggage
- **File:** `src/brief_scout/domain/ports/storage_port.py:65-74`
- **Action:**
  - Move `list_sessions` to a separate `SessionLister` port or remove it from the core storage port.

#### ISP-07 — `ConfigurationPort.reload` is unused mutability on a read interface
- **File:** `src/brief_scout/domain/ports/config_port.py:60-66`
- **Action:**
  - Move `reload()` to `ReloadableConfig`.
  - Do not force read-only clients to depend on it.

#### ISP-08 — `ConfigurationPort.get_prompt_template` is unused
- **File:** `src/brief_scout/domain/ports/config_port.py:46-58`
- **Action:**
  - Either remove the method from the port or make Agent 1’s prompt builders use it.
  - Keep the implementation honest (no silent empty returns).

#### ISP-09 — `LLMPort.complete` is unused by application clients
- **File:** `src/brief_scout/domain/ports/llm_port.py:60-74`
- **Action:**
  - Move `complete()` to `CompletionPort`.
  - Application use cases depend only on `StructuredCompletionPort`.

#### ISP-13 — `FakeLLMAdapter` exposes test-only methods outside the `LLMPort` contract
- **File:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:411-425`
- **Action:**
  - Move `get_call_log()` / `clear_call_log()` to a separate test-only mixin or fixture helper.
  - Do not expose them on the adapter used by production code.

#### ISP-14 — `FakeLLMAdapter` accepts the full `TelemetryPort` but uses only logging and event recording
- **File:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:61,324,442`
- **Action:**
  - Inject only `LoggerPort` and `EventRecorder` after the port split.

#### ISP-15 — `LangChainBaseAdapter` is a fat class-level interface with methods beyond `LLMPort`
- **File:** `src/brief_scout/infrastructure/llm/langchain_base.py:27-130`
- **Action:**
  - Refactor `LangChainBaseAdapter` to implement the new narrow ports.
  - Remove duplicated abstract methods; provide shared concrete behavior.
  - Make real LLM adapters inherit from it OR delete it if it provides no value.

### DIP

#### DIP-02 — `main._create_llm_adapter` special-cases `FakeLLMAdapter` construction
- **File:** `src/brief_scout/main.py:206-255`
- **Action:**
  - Replace with a registry-based factory.

#### DIP-03 — `LLMPort` uses an untyped `dict[str, Any]` config bag
- **File:** `src/brief_scout/domain/ports/llm_port.py:60-65, 76-81`
- **Action:**
  - Replace with a typed `LLMConfig` Pydantic model or provider-specific config subclasses.
  - If an opaque bag is still needed, document allowed keys per adapter and validate.

#### DIP-04 — Composition root directly instantiates `YAMLConfigAdapter`
- **File:** `src/brief_scout/main.py:70-75`
- **Action:**
  - Use a `ConfigurationPort` factory / registry.
  - `create_app` should receive a `ConfigurationPort` instance, not construct a concrete adapter.

#### DIP-05 — Composition root directly instantiates `LocalFileTelemetryAdapter`
- **File:** `src/brief_scout/main.py:78-86`
- **Action:**
  - Use a telemetry factory keyed by `adapter_id`.

#### DIP-06 — Storage adapter selection hard-codes concrete classes
- **File:** `src/brief_scout/main.py:95-109`
- **Action:**
  - Use a storage factory keyed by `adapter_id`.
  - Move the `"./data"` default into config, not code.

#### DIP-07 — Composition root directly instantiates `JourneyLoader`
- **File:** `src/brief_scout/main.py:127-130`
- **Action:**
  - Use a `JourneySource` factory / registry.
  - Inject `IntakeJourney` into `create_app` or construct it via factory.

#### DIP-11 — `routes.py` calls private methods on `ResearchUseCase`
- **File:** `src/brief_scout/interfaces/api/routes.py:208-213,225-227`
- **Action:**
  - Remove all `research_uc._call_*` references.
  - Call the public `ResearchPipeline` / `BriefGenerationPipeline` API.

#### DIP-12 — Routes use a service-locator pattern via `request.app.state`
- **File:** `src/brief_scout/interfaces/api/routes.py:71,104,155,162-166,392`
- **Action:**
  - Use FastAPI `Depends` providers that read from `app.state` and return typed abstractions.
  - Routes receive injected services as parameters, not pull from `request.app.state` directly.

#### DIP-13 — `FakeLLMAdapter` exposes non-port methods
- **File:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:411-425`
- **Action:**
  - Remove `get_call_log` / `clear_call_log` from the production adapter surface.
  - Provide them on a test helper or subclass.

#### DIP-14 — Real LLM adapters ignore `LangChainBaseAdapter` and duplicate logic
- **Files:** `src/brief_scout/infrastructure/llm/langchain_base.py:27-153`, `openai_adapter.py:192-269`, `claude_adapter.py:205-253`, `kimi_adapter.py:200-277`
- **Action:**
  - Centralize message building, config merging, JSON instruction injection, and schema description in `LangChainBaseAdapter` or shared mixins.
  - Each real adapter should only provide provider-specific client/message differences.

#### DIP-15 — Composition root hard-codes runtime paths and defaults
- **File:** `src/brief_scout/main.py:66,83-85,103,130`
- **Action:**
  - Move defaults (`"config"`, `"./data"`, journey path conventions) into `AppConfig` or environment-driven config.
  - `main.py` should not contain filesystem layout details.

---

## Suggested New Files

```
src/brief_scout/domain/ports/
  logger_port.py
  event_recorder_port.py
  span_context_port.py
  correlation_context_port.py
  app_config_provider_port.py
  provider_config_source_port.py
  prompt_template_provider_port.py
  session_storage_port.py
  brief_storage_port.py
  completion_port.py
  structured_completion_port.py
  template_renderer_port.py
  journey_source_port.py

src/brief_scout/infrastructure/factories/
  __init__.py
  llm_adapter_factory.py
  storage_adapter_factory.py
  telemetry_adapter_factory.py
  config_adapter_factory.py
  journey_source_factory.py

src/brief_scout/infrastructure/llm/
  fixture_repository.py
  demo_journey_player.py
  fixture_matcher.py
  shared_json_utils.py

src/brief_scout/infrastructure/telemetry/
  jsonl_writer.py
  span_store.py

src/brief_scout/infrastructure/config/
  yaml_loader.py
  config_merger.py
  env_interpolator.py
  yaml_file_journey_source.py

src/brief_scout/interfaces/api/
  dependencies.py  # FastAPI Depends providers
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
- If a test fails because it depends on Agent 1 changes, mark it as expected-integration-failure in a commit message and move on. Do not break the test suite silently.

---

## Deliverables

1. All 51 assigned concerns addressed in code.
2. New narrow ports created and old fat ports refactored/aliased.
3. Adapters split into focused, reusable components.
4. `routes.py` thinned to HTTP/SSE/DTO concerns only.
5. `main.py` uses factories/registries instead of inline concrete instantiation.
6. Passing quality gates in your branch.
7. Branch `refactor/agent-2-infrastructure-interface` pushed to origin.

---

*Do not modify Agent 1 files. When in doubt, create a new port or factory and let the integration engineer wire it to Agent 1’s consumers.*
