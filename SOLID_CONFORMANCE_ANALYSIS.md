# SOLID Conformance Analysis — `brief-scout`

**Date:** 2026-06-28  
**Scope:** `src/brief_scout` production code (~4,800 LOC)  
**Method:** Static review against the five SOLID principles. Each concern ties a concrete code location to a specific principle violation and its maintenance risk.

---

## Executive Summary

| Principle | Score | Assessment |
|---|---|---|
| Single Responsibility Principle (SRP) | **5 / 10** | Ports-and-Adapters separation exists, but major modules (routes, FakeLLM, use cases) mix transport, orchestration, prompt engineering, and persistence. |
| Open/Closed Principle (OCP) | **4 / 10** | The research pipeline, adapter selection, config models, and journey field types are closed to extension without modifying existing code. |
| Liskov Substitution Principle (LSP) | **5 / 10** | Protocols are structurally typed and too permissive; adapters diverge on error handling, metadata, side effects, and silent degradation. |
| Interface Segregation Principle (ISP) | **4 / 10** | Every domain port is wider than its clients; fat interfaces force callers to depend on methods they never use. |
| Dependency Inversion Principle (DIP) | **5 / 10** | Ports exist, but the composition root hard-codes concrete adapters and the domain/application layers leak infrastructure details. |
| **Overall** | **4.6 / 10** | The architecture is *directionally* clean, but the current ports are too coarse and the composition root is too concrete to support painless extension or swapping of adapters. |

### Scoring Rubric

| Score | Meaning |
|---|---|
| 9–10 | Exemplary: principle is consistently applied; violations are rare and trivial. |
| 7–8 | Good: minor or localized violations; easy to fix. |
| 5–6 | Moderate: clear violations in important modules; some refactoring needed. |
| 3–4 | Poor: systemic violations that impede change and testing. |
| 1–2 | Very poor: principle is largely ignored; architecture is fragile. |

---

## 1. Single Responsibility Principle (SRP) — Score: 5/10

The codebase has a recognizable Ports-and-Adapters skeleton, and the recent journey refactor did extract some responsibilities (schema, merger, checker). However, the most frequently touched modules still accumulate unrelated reasons to change: HTTP routes orchestrate the whole business pipeline, the Fake LLM adapter is a Swiss-army test harness, and every use case mixes orchestration with prompt construction. Domain models also carry presentation logic, and infrastructure adapters bundle I/O, merging, interpolation, and caching.

### Top 15 SRP Concerns

#### 1. `stream_message` route handler orchestrates the entire pipeline
- **Location:** `src/brief_scout/interfaces/api/routes.py:126-296`
- **Violation:** One async function is simultaneously the HTTP/SSE endpoint, pipeline conductor (intake → research → synthesis → brief), per-step error-recovery strategy, `ResearchBundle` assembler, session-status mutator, and SSE event formatter.
- **Risk:** Any change to pipeline ordering, resilience behavior, SSE event schema, or session lifecycle forces edits inside an HTTP route handler, coupling the web interface to the core business flow and making it hard to unit-test without FastAPI.

#### 2. `FakeLLMAdapter` is a fixture loader, matcher, demo player, latency simulator, logger, and parser
- **Location:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:44-443`
- **Violation:** The class mixes recursive fixture loading, demo-journey YAML loading, prompt-to-fixture matching with four fallback strategies, latency simulation, response serialization, call-log recording, telemetry emission, JSON/markdown parsing, and default-instance fallback.
- **Risk:** A change to test fixtures, demo data, matching heuristics, telemetry shape, or JSON parsing strategy all affect the same 443-line class; it is difficult to unit-test one path in isolation.

#### 3. `ResearchUseCase` mixes research orchestration with prompt formatting, category inference, and per-call error handling
- **Location:** `src/brief_scout/application/use_cases/research_use_case.py:33-431`
- **Violation:** The class orchestrates parallel execution, builds prompts for five distinct research domains, contains keyword-based category inference (`_infer_category`), and handles per-call telemetry/fallback logic.
- **Risk:** Changes to prompt templates or category heuristics require editing the use case. Category inference is domain knowledge that should live in its own service; prompts are configuration concerns that should be composed, not hard-coded.

#### 4. `create_app` factory couples composition-root wiring with concrete adapter selection and env parsing
- **Location:** `src/brief_scout/main.py:39-203`
- **Violation:** The function resolves env/config directories, loads configuration, instantiates concrete telemetry/storage/LLM/journey adapters, wires use cases, builds the FastAPI app, and populates `app.state`.
- **Risk:** Adding a new adapter, env var, or lifecycle hook requires editing the composition root. Extracting dedicated factories/registries would keep `create_app` focused on wiring only.

#### 5. `YAMLConfigAdapter` loads files, deep-merges, interpolates env vars, validates, caches, and reloads
- **Location:** `src/brief_scout/infrastructure/config/yaml_config_adapter.py:38-258`
- **Violation:** A single class owns YAML file I/O, default + environment overlay deep merging, `${VAR}` environment-variable interpolation, Pydantic validation, lazy caching/cache invalidation, and provider/template lookup accessors.
- **Risk:** Each concern has a different reason to change (new config source, merge semantics, env syntax, validation rules). Co-location makes the adapter brittle, and some responsibilities are duplicated separately by `JourneyLoader`.

#### 6. `IntakeUseCase` combines conversation flow, prompt engineering, extraction config, and persistence
- **Location:** `src/brief_scout/application/use_cases/intake_use_case.py:48-271`
- **Violation:** The class mutates session messages, builds the extraction prompt, knows FakeLLM-specific `demo_turn` config, merges extracted data, routes the next question, persists the session, and records telemetry.
- **Risk:** The use case is coupled to FakeLLM demo semantics. Swapping to a real LLM or changing the extraction prompt format requires touching the same class that decides conversation flow and persists sessions.

#### 7. Real LLM adapters each mix SDK client creation, request formatting, response mapping, error classification, and JSON-mode plumbing
- **Location:** `src/brief_scout/infrastructure/llm/openai_adapter.py:23-269`, `kimi_adapter.py:28-277`, `claude_adapter.py:23-253`
- **Violation:** Every real adapter re-implements lazy SDK client initialization, provider-specific message formatting, config merging, timeout/retry classification, response → `LLMResponse` mapping, JSON instruction injection, Pydantic schema description, and markdown-fence stripping.
- **Risk:** A change to JSON-mode handling, schema description, or response parsing requires editing three classes. Each adapter has four to five distinct reasons to change, and duplication amplifies maintenance cost.

#### 8. `LocalFileTelemetryAdapter` combines logging, event recording, tracing spans, correlation-ID context, and file I/O
- **Location:** `src/brief_scout/infrastructure/telemetry/local_file_adapter.py:43-246`
- **Violation:** The single adapter implements structured logs, telemetry events, distributed-tracing span lifecycle, correlation-ID context management, and daily JSONL file writing/error fallback.
- **Risk:** Logging, tracing, and correlation propagation evolve independently. A change to span storage (e.g., OpenTelemetry) or log rotation should not force changes to correlation-ID context logic.

#### 9. `IntakeJourney` mixes schema definition, field-empty logic, template rendering, question routing, and completeness evaluation
- **Location:** `src/brief_scout/domain/models/journey.py:84-203`
- **Violation:** The class holds the schema, implements field emptiness per type, renders Jinja2 templates, routes the next question, evaluates completeness, and renders the LLM extraction schema.
- **Risk:** Changes to conversation strategy, output formatting, or extraction schema representation require editing the schema class. Schema definition should be separate from flow logic and rendering.

#### 10. `Brief.to_markdown` puts presentation formatting inside a domain model
- **Location:** `src/brief_scout/domain/models/brief.py:59-187`
- **Violation:** The `Brief` model both holds structured creative-brief data and renders markdown document sections, headings, bullets, and conditional blocks.
- **Risk:** Any change to the brief’s display format (HTML, PDF, a different markdown style) forces a domain model edit. Presentation should be handled by a separate renderer/view adapter.

#### 11. `_create_llm_adapter` mixes dynamic importing with FakeLLM special-casing
- **Location:** `src/brief_scout/main.py:206-255`
- **Violation:** The helper performs dynamic module/class import, provider-specific parameter mapping, and a special branch for FakeLLM fixture/latency/demo configuration.
- **Risk:** Adding a new LLM provider or changing FakeLLM configuration shape requires editing this factory. A provider registry that maps config to constructor kwargs would keep the factory generic.

#### 12. `SynthesisUseCase` fuses orchestration, prompt building, and source attachment
- **Location:** `src/brief_scout/application/use_cases/synthesis_use_case.py:24-160`
- **Violation:** The class builds the synthesis prompt (JSON serialization + template substitution), invokes the LLM structured completion, assigns `Brief.sources`, and records telemetry.
- **Risk:** A change to prompt template strategy or source-attachment rules touches the same class that defines the synthesis workflow.

#### 13. `routes.py` module overall is a kitchen-sink interface layer
- **Location:** `src/brief_scout/interfaces/api/routes.py:1-400`
- **Violation:** The module contains route definitions, direct storage reads/writes, DTO construction from domain models, pipeline coordination, SSE event serialization, and the dead helper `_dict_to_intake_data` (lines 299-316).
- **Risk:** The interface layer is not a thin adapter; it owns application flow and persistence calls, making it impossible to reuse the business flows in a CLI, worker, or test without the FastAPI machinery.

#### 14. `IntakeData` data model embeds completeness rules and scoring
- **Location:** `src/brief_scout/domain/models/intake.py:21-71`
- **Violation:** The model holds intake fields but also defines a hard-coded `is_complete` property and `completion_score` calculation.
- **Risk:** The journey schema is now the authoritative completeness source, yet the model still carries a legacy rule. Changing required fields means updating both the journey and this model, risking inconsistency.

#### 15. `CompletenessChecker` couples evaluation logic with telemetry emission
- **Location:** `src/brief_scout/domain/services/completeness_checker.py:35-90`
- **Violation:** The domain service evaluates completeness against the journey schema and also logs structured telemetry events.
- **Risk:** A change to observability requirements (what to log, which level, event naming) forces edits to a domain service. Pure domain logic should return a result; telemetry should be added by the caller or via a decorator/interceptor.


---

## 2. Open/Closed Principle (OCP) — Score: 4/10

The architecture is open *in spirit* because new adapters can be introduced, but in practice most extension points are closed. The five research steps are enumerated in the use case, duplicated in the streaming route, baked into `ResearchBundle`, and enumerated again in `PromptsConfig`. Adapter selection uses hard-coded `if/else` branches rather than registries. Even the schema-driven journey remains partially closed because field types and the `IntakeData` model itself are concrete and fixed.

### Top 15 OCP Concerns

#### 1. Research pipeline hard-codes the “5 research calls”
- **Location:** `src/brief_scout/application/use_cases/research_use_case.py:57-121` and `src/brief_scout/interfaces/api/routes.py:189-261`
- **Violation:** `ResearchUseCase.execute()` explicitly calls the five `_call_*` methods and unpacks results by positional index; the SSE route repeats the same closed list of step names, call methods, default models, and positional `ResearchBundle` assembly.
- **Risk:** Adding a new research dimension (e.g., “Market Sizing”) requires editing both the use case and the route layer. There is no `ResearchStrategy` plugin point.

#### 2. `ResearchBundle` is a closed aggregate of five concrete result types
- **Location:** `src/brief_scout/domain/models/research.py:104-118`
- **Violation:** The model schema hard-codes five result fields.
- **Risk:** Any new research step forces a schema change in the domain model, which then ripples through synthesis prompts, tests, and the streaming API.

#### 3. `PromptsConfig` enumerates a fixed set of prompt templates
- **Location:** `src/brief_scout/domain/models/config.py:31-42`
- **Violation:** The config model has explicit fields for each research prompt and synthesis and does not allow `extra="allow"`.
- **Risk:** A new prompt added to YAML is ignored by Pydantic validation. Extending the prompt catalog requires modifying the domain config model.

#### 4. Storage adapter selection is a hard-coded `if/else`
- **Location:** `src/brief_scout/main.py:95-109`
- **Violation:** The composition root branches on `file_system` versus a default `in_memory` adapter.
- **Risk:** Adding a database, Redis, or S3 adapter means editing the composition root. There is no registry or factory mapping adapter names to callables.

#### 5. Telemetry adapter is instantiated as a concrete `LocalFileTelemetryAdapter`
- **Location:** `src/brief_scout/main.py:78-93`
- **Violation:** The `telemetry.adapter` config key is read but never used to select an implementation.
- **Risk:** Swapping to OpenTelemetry, Datadog, or stdout telemetry requires changing `main.py` rather than registering a new adapter.

#### 6. LLM factory special-cases `FakeLLMAdapter` and uses a fixed constructor signature
- **Location:** `src/brief_scout/main.py:206-255`
- **Violation:** FakeLLM gets its own constructor branch (fixture/latency/demo parameters); real adapters are constructed with a single generic signature.
- **Risk:** A new adapter needing different constructor arguments (e.g., `region`, `project_id`, `endpoint`) or a different fake/test adapter requires editing `_create_llm_adapter`.

#### 7. SSE stream route re-implements the research step orchestration
- **Location:** `src/brief_scout/interfaces/api/routes.py:189-261`
- **Violation:** The route builds its own `research_calls`, `default_map`, and positional `ResearchBundle` rather than delegating to an extensible pipeline object.
- **Risk:** The streaming behavior and the research use case must be kept in sync manually. A new research step cannot be added in one place.

#### 8. Category inference uses a closed keyword map
- **Location:** `src/brief_scout/application/use_cases/research_use_case.py:351-431`
- **Violation:** A keyword dictionary for industries/categories is embedded in the use case.
- **Risk:** Adding a new industry/category requires modifying the use case. There is no strategy or registry for category classifiers.

#### 9. Journey field types are a closed literal
- **Location:** `src/brief_scout/domain/models/journey.py:19` and `src/brief_scout/domain/services/intake_data_merger.py:63-73`
- **Violation:** `FieldType = Literal["string", "list", "object"]`. `is_empty()`, `render_extraction_schema()`, and `IntakeDataMerger._merge_field()` all branch on these three values.
- **Risk:** Supporting a new field type such as `number`, `boolean`, or `date` requires editing multiple domain files.

#### 10. Each research call has its own hard-coded prompt-formatting method
- **Location:** `src/brief_scout/application/use_cases/research_use_case.py:122-263`
- **Violation:** `_call_brand_audit`, `_call_competitor_scan`, etc., each know the exact `IntakeData` fields and config keys they need.
- **Risk:** A new research type cannot be added by dropping in a new class; a new method and prompt config field must be written.

#### 11. Synthesis prompt placeholders are hard-coded
- **Location:** `src/brief_scout/application/use_cases/synthesis_use_case.py:124-160`
- **Violation:** The code calls `user_content.replace("{intake_json}", ...)` and `replace("{research_json}", ...)`.
- **Risk:** Changing the synthesis input format (e.g., adding `{brand_voice_json}`) requires editing the use case. There is no template-variable discovery mechanism.

#### 12. Session status values are duplicated as string literals across layers
- **Location:** `src/brief_scout/domain/models/intake.py:92`, `src/brief_scout/application/dto/intake_dto.py:39`, `src/brief_scout/application/use_cases/intake_use_case.py:138,153`, `src/brief_scout/interfaces/api/routes.py:270`
- **Violation:** Status strings (`"intaking"`, `"researching"`, `"synthesizing"`, `"complete"`) are repeated in the domain model, DTO, use case, and route.
- **Risk:** Adding a new pipeline phase means updating the domain model, DTO, use case, and route. The literal strings also prevent compile-time safety beyond Pydantic.

#### 13. `IntakeData` fields are fixed in code
- **Location:** `src/brief_scout/domain/models/intake.py:21-37`
- **Violation:** The data container is a concrete Pydantic model with fixed attributes.
- **Risk:** Although the journey YAML drives the interview, adding a new intake field still requires adding an attribute to `IntakeData`. The schema-driven journey is not fully closed against new fields.

#### 14. `YAMLConfigAdapter` hard-codes file names and YAML source
- **Location:** `src/brief_scout/infrastructure/config/yaml_config_adapter.py:150-194`
- **Violation:** Uses `default.yaml` and `{env}.yaml` directly.
- **Risk:** Switching to remote config, vault-backed config, or a different file naming convention requires editing the adapter rather than injecting a new loader.

#### 15. `JourneyLoader` hard-codes file names and YAML format
- **Location:** `src/brief_scout/infrastructure/config/journey_loader.py:39-70`
- **Violation:** Uses `journey.yaml` and `journey.{env}.yaml` directly.
- **Risk:** Loading journeys from a database, remote CMS, or JSON requires modifying the loader. There is no `JourneySource` abstraction.


---

## 3. Liskov Substitution Principle (LSP) — Score: 5/10

Mypy strict passes, so the structural types are technically compatible. The LSP problems are therefore *behavioral*: port implementations silently degrade results, raise unexpected exceptions, or produce different side effects. The Fake LLM adapter—the primary MVP adapter—deviates most from the real adapters, so substituting it changes failure semantics, metadata shape, and content serialization. File and config adapters also fail to honor `| None` return contracts consistently.

### Top 15 LSP Concerns

#### 1. `FakeLLMAdapter.complete_structured` weakens the failure post-condition
- **Location:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:337-400`
- **Violation:** Real adapters raise `LLMCallError` on JSON/validation failures. `FakeLLMAdapter` returns a default empty instance for most parse failures.
- **Risk:** Code that depends on detecting bad LLM output (retry logic, tests, telemetry alerts) behaves differently when the fake adapter is substituted. The research use case’s fallback path is effectively dead code with the fake adapter, masking fixture data problems.

#### 2. `FileSystemStorageAdapter.get_session` raises on corrupted files
- **Location:** `src/brief_scout/infrastructure/storage/file_system_adapter.py:65-77`
- **Violation:** `BriefStoragePort.get_session` promises `ChatSession | None`. The file-system implementation calls `ChatSession.model_validate_json(...)`, which can raise `ValidationError` on malformed files.
- **Risk:** Swapping `InMemoryStorageAdapter` for `FileSystemStorageAdapter` can crash callers that only handle `None`. A port consumer cannot safely treat all implementations uniformly.

#### 3. `YAMLConfigAdapter.get_prompt_template` silently degrades string-valued templates
- **Location:** `src/brief_scout/infrastructure/config/yaml_config_adapter.py:109-137`
- **Violation:** The protocol says the method returns a `PromptTemplateConfig` for the named template and raises `KeyError` if not found. For string-valued prompts, the adapter returns an empty `PromptTemplateConfig`, discarding the configured string.
- **Risk:** A valid configuration produces empty system/user prompts for string templates. A caller cannot rely on the returned config actually containing the configured data.

#### 4. `ClaudeAdapter` silently drops system-role context items
- **Location:** `src/brief_scout/infrastructure/llm/claude_adapter.py:205-218`
- **Violation:** `OpenAIAdapter` and `KimiAdapter` preserve all `Prompt.context` entries, including `role="system"`. `ClaudeAdapter` explicitly strips them.
- **Risk:** The same `Prompt` object yields semantically different API requests depending on the adapter. Prompts that rely on system-role context are silently weakened when Claude is substituted.

#### 5. `TelemetryPort.log` accepts `str` without a normalization contract
- **Location:** `src/brief_scout/domain/ports/telemetry_port.py:55-60` and `src/brief_scout/infrastructure/telemetry/local_file_adapter.py:81-107`
- **Violation:** The protocol types `level` as `LogLevel | str`. `LocalFileTelemetryAdapter` normalizes strings via `level.upper()` and then constructs `LogLevel(...)`, raising `ValueError` for invalid strings. The protocol documents no such exception.
- **Risk:** A port consumer passing a lowercase or misspelled level string may work with one adapter and crash with another. The overly broad type makes implementations non-substitutable.

#### 6. `LocalFileTelemetryAdapter.start_span` mutates correlation ID
- **Location:** `src/brief_scout/infrastructure/telemetry/local_file_adapter.py:134-177`
- **Violation:** The protocol only says to start a span and return an ID. The local-file implementation has the side effect of calling `set_correlation_id`.
- **Risk:** Other plausible implementations (OpenTelemetry, stdout) may not set correlation ID on span start. Callers that depend on this side effect are coupled to the local-file adapter; conversely, callers that assume spans are side-effect-free are broken by it.

#### 7. LLM adapters do not explicitly declare `LLMPort` implementation
- **Location:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:44`, `openai_adapter.py:23`, `claude_adapter.py:23`, `kimi_adapter.py:28`, `langchain_base.py:27`
- **Violation:** Adapters rely entirely on structural subtyping. None inherit from `LLMPort`, and `LangChainBaseAdapter` is an `ABC` that does not include `LLMPort` either.
- **Risk:** Runtime has no contract knowledge (`isinstance(x, LLMPort)` is false because the protocols are not `@runtime_checkable`). A missing or renamed method is only caught when the adapter is used as a port, making substitution risky.

#### 8. `LocalFileTelemetryAdapter.end_span` swallows unknown span IDs
- **Location:** `src/brief_scout/infrastructure/telemetry/local_file_adapter.py:179-207`
- **Violation:** The protocol is silent on invalid span IDs. The local adapter logs a warning and returns. A tracing-oriented implementation would typically raise `KeyError` or similar.
- **Risk:** Error-handling code that works with one telemetry adapter may not work with another. The lack of a specified post-condition makes the port implementations behaviorally non-substitutable.

#### 9. `ResearchUseCase` error-handling path diverges by adapter
- **Location:** `src/brief_scout/application/use_cases/research_use_case.py:265-326`
- **Violation:** `_execute_single_research` catches `Exception` from `complete_structured` and returns a default instance. Because `FakeLLMAdapter` already returns a default instance on parse failure, the `except` branch is never reached with the fake adapter.
- **Risk:** Substituting adapters changes observable behavior (telemetry events, logged errors, fallback reasons). The use case is not portable across valid `LLMPort` implementations.

#### 10. `IntakeUseCase` extraction error handling is adapter-dependent
- **Location:** `src/brief_scout/application/use_cases/intake_use_case.py:121-130` and `183-252`
- **Violation:** `_extract_structured_data` wraps failures in `LLMCallError`; `process_message` catches `BriefScoutError` to preserve existing data. With `FakeLLMAdapter`, parse failures return an empty default `IntakeData`, bypassing the catch and potentially overwriting the session with empty extracted data.
- **Risk:** Substituting the fake adapter for a real one changes whether and how extraction failures are handled, potentially corrupting collected intake data.

#### 11. `FileSystemStorageAdapter.list_sessions` silently skips corrupted files
- **Location:** `src/brief_scout/infrastructure/storage/file_system_adapter.py:103-128`
- **Violation:** The protocol says to return recent sessions. The file-system adapter skips files that fail validation with a bare `except Exception`.
- **Risk:** A caller gets an incomplete list with no error signal. Behavior differs from `InMemoryStorageAdapter`, where such corruption cannot occur.

#### 12. `FakeLLMAdapter.complete` serializes dict responses as JSON strings
- **Location:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:251-335`
- **Violation:** Real adapters return the LLM’s raw string content. The fake adapter stringifies fixture dicts to JSON, so `response.content` is often a JSON blob rather than natural text.
- **Risk:** Callers using `complete()` for prose output receive JSON when the fake adapter is substituted, breaking the semantic post-condition of `LLMResponse.content`.

#### 13. `LLMResponse.metadata` shape differs across adapters
- **Location:** `fake_llm_adapter.py:305-308`, `openai_adapter.py:113-118`, `claude_adapter.py:129-132`, `kimi_adapter.py:121-127`
- **Violation:** The protocol types `metadata` as `dict[str, Any]` but each adapter populates different, provider-specific keys (`fixture_name`, `prompt_tokens`, `stop_sequence`, `base_url`, etc.).
- **Risk:** Consumers of `metadata` cannot rely on a common schema. A telemetry/dashboard feature built against one adapter breaks when another `LLMPort` is substituted.

#### 14. `LangChainBaseAdapter._handle_error` depends on an abstract property
- **Location:** `src/brief_scout/infrastructure/llm/langchain_base.py:132-153`
- **Violation:** A concrete (non-abstract) base method calls `self.provider_name`, which is `@abstractmethod`. Subclasses must implement it before `_handle_error` can be used.
- **Risk:** A subclass that overrides `_handle_error` without providing `provider_name` can produce confusing runtime errors. The base class implicitly strengthens the precondition for subclasses.

#### 15. `ConfigurationPort.reload()` contract is under-specified
- **Location:** `src/brief_scout/domain/ports/config_port.py:60-66` and `src/brief_scout/infrastructure/config/yaml_config_adapter.py:139-148`
- **Violation:** The protocol says “Reload configuration from source” but does not specify when reloaded values become visible or what exceptions may be raised. `YAMLConfigAdapter` clears a cached property; a different implementation might reload eagerly or lazily.
- **Risk:** Callers cannot safely assume that a value read immediately after `reload()` reflects the new configuration. Swapping config adapters can introduce subtle staleness or timing bugs.


---

## 4. Interface Segregation Principle (ISP) — Score: 4/10

Every major domain port is wider than the clients that consume it. `TelemetryPort` bundles logging, events, tracing, and correlation context. `ConfigurationPort` exposes the entire `AppConfig` aggregate plus provider/prompt lookups plus reload. `BriefStoragePort` forces session-only clients to depend on brief methods and vice versa. `LLMPort` exposes both generic and structured completion even though application code only ever uses the structured path. The result is that changes to any single port method can theoretically affect every implementer or client.

### Top 15 ISP Concerns

#### 1. `TelemetryPort` bundles logging, events, tracing, and correlation context
- **Location:** `src/brief_scout/domain/ports/telemetry_port.py:48-119`
- **Violation:** The protocol declares six unrelated capabilities (`log`, `record_event`, `start_span`, `end_span`, `get_correlation_id`, `set_correlation_id`). Clients use very different subsets.
- **Risk:** Any change to span signatures, event shape, or correlation semantics forces every use case, service, and adapter to be re-checked/recompiled. A split into `LoggerPort`, `EventRecorder`, and `SpanContext`/`CorrelationContext` would narrow dependencies.

#### 2. `ConfigurationPort` mixes app config, provider lookup, prompt lookup, and reload
- **Location:** `src/brief_scout/domain/ports/config_port.py:16-66`
- **Violation:** The port combines `app_config`, `get_provider_config`, `get_prompt_template`, and `reload`. Use cases only need prompt templates, `main.py` only needs provider config, and the health route only needs version/provider lists.
- **Risk:** Prompt-only clients are coupled to provider-config and hot-reload semantics. A `PromptTemplateProvider` and `ProviderConfigSource` would isolate them.

#### 3. `BriefStoragePort` merges session and brief persistence
- **Location:** `src/brief_scout/domain/ports/storage_port.py:18-74`
- **Violation:** One protocol covers both `ChatSession` persistence (`save_session`, `get_session`, `list_sessions`) and `Brief` persistence (`save_brief`, `get_brief`). No client in `src` uses all five methods.
- **Risk:** A session-only store must still implement brief methods and import the `Brief` model, and vice versa. Splitting into `SessionStoragePort` and `BriefStoragePort` would let clients depend only on the entity they touch.

#### 4. `LLMPort` combines generic and structured completion
- **Location:** `src/brief_scout/domain/ports/llm_port.py:53-104`
- **Violation:** The port declares both `complete` and `complete_structured`. All application use cases (`IntakeUseCase`, `ResearchUseCase`, `SynthesisUseCase`) only call `complete_structured`.
- **Risk:** Research and synthesis clients depend on a lower-level completion method they never invoke. A `StructuredCompletionPort` (and a wider `LLMPort` that extends it for adapters) would fix this.

#### 5. `ConfigurationPort.app_config` exposes the entire `AppConfig` aggregate
- **Location:** `src/brief_scout/domain/ports/config_port.py:23-30` and `src/brief_scout/domain/models/config.py:56-75`
- **Violation:** The port returns the full `AppConfig` Pydantic model. Use cases navigate only to `app_config.prompts.*`; the health route uses only `app_version`/`llm_providers`.
- **Risk:** Clients are coupled to telemetry, storage, and provider settings they never read. Returning narrower interfaces such as `PromptsProvider`/`AppMetadataProvider` would isolate them.

#### 6. `BriefStoragePort.list_sessions` is unused interface baggage
- **Location:** `src/brief_scout/domain/ports/storage_port.py:65-74`
- **Violation:** No client in `src` calls `list_sessions`. Both `InMemoryStorageAdapter` and `FileSystemStorageAdapter` still implement and test it.
- **Risk:** Dead weight in every adapter; changes to listing semantics affect all storage implementations even though the feature is not consumed.

#### 7. `ConfigurationPort.reload` is unused mutability on a read interface
- **Location:** `src/brief_scout/domain/ports/config_port.py:60-66`
- **Violation:** `reload()` is declared on the port, but no client in `src` calls it.
- **Risk:** Read-only clients are coupled to a mutable lifecycle operation, and adapters must support hot-reload semantics that the application does not currently use.

#### 8. `ConfigurationPort.get_prompt_template` is unused
- **Location:** `src/brief_scout/domain/ports/config_port.py:46-58`
- **Violation:** The named-template lookup method is implemented by `YAMLConfigAdapter` but never called. Use cases instead access `config.app_config.prompts.research_*` and `prompts.synthesis` directly.
- **Risk:** Implementers must maintain an API that has no callers, and the port advertises a retrieval style that the codebase does not actually use.

#### 9. `LLMPort.complete` is unused by application clients
- **Location:** `src/brief_scout/domain/ports/llm_port.py:60-74`
- **Violation:** `complete()` is declared, but every use case calls only `complete_structured`. It is invoked only inside adapter internals (e.g., `OpenAIAdapter.complete_structured` → `self.complete`).
- **Risk:** Application-layer clients carry a dependency on a method that is an implementation detail of adapters.

#### 10. `CompletenessChecker` depends on the full `TelemetryPort` for one method
- **Location:** `src/brief_scout/domain/services/completeness_checker.py:35-90`
- **Violation:** The constructor requires `TelemetryPort`, but the service only calls `telemetry.log(...)`.
- **Risk:** The service is over-constrained; it cannot accept a simple logger implementation even though it only logs.

#### 11. `IntakeUseCase` depends on the full `BriefStoragePort` only to save sessions
- **Location:** `src/brief_scout/application/use_cases/intake_use_case.py:48-271`
- **Violation:** The use case is injected with `BriefStoragePort` but only calls `await self._storage.save_session(session)`.
- **Risk:** A narrower `SessionWriter` port would suffice. Tests must stub methods for brief retrieval even though they are never exercised.

#### 12. `ResearchUseCase` and `SynthesisUseCase` depend on the full `LLMPort` only for structured completion
- **Location:** `src/brief_scout/application/use_cases/research_use_case.py:49,294` and `src/brief_scout/application/use_cases/synthesis_use_case.py:39,82`
- **Violation:** Both use cases are typed to `LLMPort` but only call `complete_structured`.
- **Risk:** They cannot be wired to a narrower `StructuredCompletionPort`, and they are coupled to the generic `complete` method.

#### 13. `FakeLLMAdapter` exposes test-only methods outside the `LLMPort` contract
- **Location:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:411-425`
- **Violation:** `get_call_log()` and `clear_call_log()` are public, but they are not part of `LLMPort`.
- **Risk:** Any test or helper that uses them must depend on the concrete `FakeLLMAdapter` rather than the port, breaking the abstraction.

#### 14. `FakeLLMAdapter` accepts the full `TelemetryPort` but uses only logging and event recording
- **Location:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:61,324,442`
- **Violation:** The constructor is typed `TelemetryPort | None`, yet the adapter only calls `log` and `record_event`.
- **Risk:** It is forced to depend on span/correlation capabilities it never uses; a `LoggerPort`/`EventRecorder` split would let it declare exactly what it needs.

#### 15. `LangChainBaseAdapter` is a fat class-level interface with methods beyond `LLMPort`
- **Location:** `src/brief_scout/infrastructure/llm/langchain_base.py:27-130`
- **Violation:** The ABC adds `_create_client()` and `_format_messages()` abstract methods on top of the `LLMPort`-equivalent `complete`, `complete_structured`, and `provider_name`. It is not a `Protocol`, not marked as implementing `LLMPort`, and has no concrete subclasses in `src`.
- **Risk:** If real adapters subclass it, they are forced to implement provider-specific client creation and message formatting even when the provider SDK handles formatting. It also duplicates the `LLMPort` contract, creating two sources of truth for the LLM interface.


---

## 5. Dependency Inversion Principle (DIP) — Score: 5/10

High-level modules do depend on ports (Protocols) rather than concrete adapters in most constructor signatures, which is the right direction. The inversion breaks down in three places: (1) the composition root directly instantiates concrete adapters and hard-codes adapter selection; (2) the application/domain layers know infrastructure details (FakeLLM demo turns, Jinja2, concrete class path strings); and (3) the `LLMPort` config bag is an untyped `dict[str, Any]` that lets adapter-specific keys leak upward. The result is that swapping adapters usually still requires code changes.

### Top 15 DIP Concerns

#### 1. `IntakeUseCase` builds FakeLLM-specific `demo_turn` config
- **Location:** `src/brief_scout/application/use_cases/intake_use_case.py:254-271`
- **Violation:** The application layer explicitly knows that the configured LLM is a `FakeLLMAdapter` and that it understands a `demo_turn` key. It uses the generic `LLMPort.complete_structured(..., config=...)` bag to push adapter-specific data.
- **Risk:** You cannot swap to a real LLM without this leakage becoming dead/invalid config. The port abstraction is bypassed, and the use case is coupled to a low-level test adapter.

#### 2. `main._create_llm_adapter` special-cases `FakeLLMAdapter` construction
- **Location:** `src/brief_scout/main.py:206-255`
- **Violation:** The composition root encodes the concrete constructor signature and config schema of `FakeLLMAdapter`. Real adapters are constructed generically, but the fake adapter gets its own branch.
- **Risk:** Changing `FakeLLMAdapter.__init__` or its config keys requires editing `main.py`. A new adapter with extra constructor needs would need another special branch.

#### 3. `LLMPort` uses an untyped `dict[str, Any]` config bag
- **Location:** `src/brief_scout/domain/ports/llm_port.py:60-65, 76-81`
- **Violation:** The port does not abstract configuration. It accepts an opaque dictionary, so callers must know provider-specific keys (`demo_turn`, `fixture_name`, `latency_ms`, etc.).
- **Risk:** Adapter swaps become risky—valid config for one adapter may be meaningless or wrong for another. This directly enables concerns #1 and #2.

#### 4. Composition root directly instantiates `YAMLConfigAdapter`
- **Location:** `src/brief_scout/main.py:70-75`
- **Violation:** `main.py` depends on a concrete config infrastructure adapter instead of receiving a `ConfigurationPort` from a factory or bootstrapper.
- **Risk:** Switching to environment-variable config, a remote config service, or a test stub requires modifying the composition root.

#### 5. Composition root directly instantiates `LocalFileTelemetryAdapter`
- **Location:** `src/brief_scout/main.py:78-86`
- **Violation:** The high-level application factory is coupled to a specific telemetry backend (local JSONL files).
- **Risk:** Replacing telemetry with OpenTelemetry, stdout, or a test spy requires editing `main.py`.

#### 6. Storage adapter selection hard-codes concrete classes
- **Location:** `src/brief_scout/main.py:95-109`
- **Violation:** A string-to-concrete-class mapping plus inline imports lives in the composition root. The `"./data"` path is also hard-coded.
- **Risk:** Adding a database or S3 adapter means editing `main.py` and the branch logic. The storage choice is not resolved by a plugin/factory abstraction.

#### 7. Composition root directly instantiates `JourneyLoader`
- **Location:** `src/brief_scout/main.py:127-130`
- **Violation:** Journey loading is an infrastructure concern, yet the application factory depends on the concrete `JourneyLoader`.
- **Risk:** Loading the intake schema from a database, CMS, or test dictionary requires changing `main.py`. The domain’s journey source is not abstracted.

#### 8. Domain model `IntakeJourney` depends on Jinja2
- **Location:** `src/brief_scout/domain/models/journey.py:12,71,79,187`
- **Violation:** The domain layer imports and uses a concrete templating engine directly inside a domain model.
- **Risk:** The domain layer is no longer framework-agnostic. Replacing Jinja2 or running domain logic without it installed is impossible.

#### 9. `IntakeUseCase` depends on Jinja2
- **Location:** `src/brief_scout/application/use_cases/intake_use_case.py:14,215-218`
- **Violation:** The application layer directly couples prompt templating to Jinja2 instead of using a templating port or service.
- **Risk:** The templating engine cannot be swapped; application tests must provide Jinja2; template logic is scattered between use case and domain model.

#### 10. Domain config models encode concrete infrastructure names/class paths
- **Location:** `src/brief_scout/domain/models/config.py:13,50,67,68,71`
- **Violation:** The domain’s configuration schema stores strings that name concrete adapters and class paths (`LLMProviderConfig.adapter_class`, `storage_adapter`, `telemetry.adapter`).
- **Risk:** Adding/removing adapters requires domain config changes; the config model cannot validate that the named adapter actually exists.

#### 11. `routes.py` calls private methods on `ResearchUseCase`
- **Location:** `src/brief_scout/interfaces/api/routes.py:208-213,225-227`
- **Violation:** The interface layer depends on underscored, private methods of a concrete use case. These are implementation details, not a published abstraction.
- **Risk:** Refactoring `ResearchUseCase` internals (e.g., renaming, adding common retry logic) breaks the route layer. A proper public port/contract is missing.

#### 12. Routes use a service-locator pattern via `request.app.state`
- **Location:** `src/brief_scout/interfaces/api/routes.py:71,104,155,162-166,392`
- **Violation:** Routes depend on a global state bag rather than injected abstractions. While the attributes implement ports, the route layer is coupled to the composition root’s naming and lifecycle.
- **Risk:** Routes are harder to unit-test in isolation; hidden dependencies make the dependency graph unclear.

#### 13. `FakeLLMAdapter` exposes non-port methods
- **Location:** `src/brief_scout/infrastructure/llm/fake_llm_adapter.py:411-425`
- **Violation:** `get_call_log()` and `clear_call_log()` are not part of `LLMPort`. Any caller that needs them must depend on the concrete `FakeLLMAdapter`.
- **Risk:** Test utilities or diagnostics will couple to the fake adapter. Swapping to a real LLM breaks anything relying on the call log, because the port contract is incomplete.

#### 14. Real LLM adapters ignore `LangChainBaseAdapter` and duplicate logic
- **Location:** `src/brief_scout/infrastructure/llm/langchain_base.py:27-153` (unused base); `openai_adapter.py:192-269`, `claude_adapter.py:205-253`, `kimi_adapter.py:200-277`
- **Violation:** A shared `LangChainBaseAdapter` abstraction exists, but `OpenAIAdapter`, `ClaudeAdapter`, and `KimiAdapter` reimplement `_build_messages`, `_merge_config`, `_inject_json_instructions`, and `_describe_schema` independently.
- **Risk:** The declared base provides no actual inversion; common behavior is duplicated across concrete adapters, increasing maintenance and the risk of inconsistent JSON handling.

#### 15. Composition root hard-codes runtime paths and defaults
- **Location:** `src/brief_scout/main.py:66,83-85,103,130`
- **Violation:** Concrete filesystem layout and defaults (`"config"`, `"./data"`, journey file path convention) are embedded in the composition root.
- **Risk:** Deploying in environments with different path conventions requires code changes rather than external configuration.

---

## Recommendations

1. **Introduce a pipeline abstraction for research.** Replace the five hard-coded `_call_*` methods and the route-level orchestration with a `ResearchStrategy` registry that maps step names to callable strategies and produces a generic `ResearchBundle`.
2. **Split the fat ports.** Decompose `TelemetryPort`, `ConfigurationPort`, `BriefStoragePort`, and `LLMPort` into role-specific protocols so clients depend only on what they use.
3. **Make the composition root configuration-driven.** Replace adapter `if/else` branches and inline imports with a registry/factory that resolves adapter names from config to constructor callables, and inject concrete filesystem paths from config.
4. **Remove infrastructure details from domain/application layers.** Move Jinja2 rendering and FakeLLM `demo_turn` logic out of domain models and use cases; introduce a templating port and a demo-mode abstraction.
5. **Strengthen port contracts.** Specify and normalize error handling (raise vs. default), metadata schemas, log-level normalization, and config bag shapes so adapters are truly substitutable.
6. **Separate presentation from domain models.** Move `Brief.to_markdown` and `IntakeJourney` template rendering into dedicated renderer adapters.

---

*End of analysis — 75 concerns across the five SOLID principles.*
