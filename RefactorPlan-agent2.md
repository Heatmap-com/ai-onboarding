# Refactor Plan — Agent 2: Infrastructure & Interface Layer SOLID Cleanup

## Branch
`refactor/agent-solid-infra-interface`

## Goal
Raise **OCP**, **DIP**, and **LSP** grades for infrastructure, interfaces, and adapters by:
1. Making search-tool and storage-adapter selection extensible through factories.
2. Injecting the markdown renderer into API routes.
3. Aligning fake-adapter error semantics with real adapters.

## Target SOLID lift

| Principle | Current | Target | How this wave contributes |
|-----------|---------|--------|---------------------------|
| SRP       | B+      | A-     | Routes no longer construct renderers; telemetry adapter remains as-is. |
| OCP       | C+      | B+     | Search tool and storage adapter factories are registry-based. |
| LSP       | C+      | B      | Fake LLM adapter fails with `LLMCallError` like real adapters. |
| ISP       | B+      | A-     | Narrow factory/search ports added; routes depend on renderer port. |
| DIP       | C       | B+     | Routes depend on injected renderer; main.py will depend on factories. |

## Pre-requisites
- Read `src/brief_scout/infrastructure/factories/`, `src/brief_scout/infrastructure/llm/`, `src/brief_scout/interfaces/api/`, and `src/brief_scout/main.py`.
- Do **not** edit `src/brief_scout/main.py`; the integration wave will wire your new factories and dependencies there.
- Do **not** edit domain/application ports except to add new infrastructure-facing ports if needed.

## Tasks

### 1. Create an extensible `SearchToolFactory`
- Create `src/brief_scout/domain/ports/search_tool_factory_port.py` with a `SearchToolFactory` Protocol:
  ```python
  class SearchToolFactory(Protocol):
      def create(self, config: SearchConfig) -> ResearchTool: ...
  ```
- Create `src/brief_scout/infrastructure/factories/search_tool_factory.py` with a registry-based implementation.
  - Register `"fake"` → `FakeSearchTool()`.
  - Register `"tavily"` → `TavilyWebSearchTool(...)` when `api_key` is present; otherwise fall back to `FakeSearchTool()`.
- Update `src/brief_scout/infrastructure/factories/__init__.py` to export `SearchToolFactory` and the concrete factory.

### 2. Generalize `StorageAdapterFactory`
- Refactor `src/brief_scout/infrastructure/factories/storage_adapter_factory.py`:
  - Change `_REGISTRY` from `dict[str, type[Any]]` to `dict[str, Callable[..., BriefStoragePort]]`.
  - Register `"in_memory"` as a callable that returns `InMemoryStorageAdapter()`.
  - Register `"file_system"` as a callable that returns `FileSystemStorageAdapter(data_dir=str(data_dir), logger=logger)`.
  - Remove the `if adapter_cls is FileSystemStorageAdapter:` special-case branch.
  - `create()` looks up the callable and invokes it with `data_dir` and `logger`.
- If needed, update `InMemoryStorageAdapter.__init__` to accept and ignore `**_kwargs` so the universal callable signature is safe.

### 3. Inject `BriefMarkdownRenderer` into routes
- Add `get_brief_markdown_renderer(request: Request) -> BriefMarkdownRenderer` in `src/brief_scout/interfaces/api/dependencies.py`.
- Update `src/brief_scout/interfaces/api/routes.py`:
  - Remove direct `from brief_scout.application.services.brief_markdown_renderer import BriefMarkdownRenderer` imports if they are only used for instantiation.
  - Add `renderer: Annotated[BriefMarkdownRenderer, Depends(get_brief_markdown_renderer)]` to `send_message`, `run_pipeline`, and `get_brief`.
  - Use the injected renderer instead of constructing `BriefMarkdownRenderer()` inline.
- The integration wave will store a `BriefMarkdownRenderer` instance on `app.state.brief_markdown_renderer` in `main.py`.

### 4. Align `FakeLLMAdapter` error semantics (LSP)
- In `src/brief_scout/infrastructure/llm/fake_llm_adapter.py`, tighten `complete_structured` so that missing/invalid fixture data always raises `LLMCallError` (retryable=False) instead of silently producing an empty model.
- Verify the production fake adapter already raises on empty string, non-dict, validation failure; add an explicit guard for the case where `fixture_data.get("response", {})` is an empty dict.
- Update `tests/unit/test_fake_llm_adapter.py` to assert the raised `LLMCallError` for bad fixtures.

### 5. Interface/infrastructure test cleanup
- Delete or rewrite `tests/integration/test_api.py` so it tests the real FastAPI app (like `test_api_source.py`) rather than a hand-rolled `TestAPIBackend`.
- Update `tests/unit/test_storage_adapters.py` to cover the generalized factory behavior (e.g. custom registry).
- Update any test that directly imports the inline application `Jinja2TemplateRenderer` (Agent 1 is deleting it).

## Files you will touch

### Create
- `src/brief_scout/domain/ports/search_tool_factory_port.py`
- `src/brief_scout/infrastructure/factories/search_tool_factory.py`

### Modify
- `src/brief_scout/infrastructure/factories/storage_adapter_factory.py`
- `src/brief_scout/infrastructure/factories/__init__.py`
- `src/brief_scout/infrastructure/llm/fake_llm_adapter.py`
- `src/brief_scout/infrastructure/storage/in_memory_adapter.py` (if `**_kwargs` needed)
- `src/brief_scout/interfaces/api/dependencies.py`
- `src/brief_scout/interfaces/api/routes.py`
- `tests/unit/test_fake_llm_adapter.py`
- `tests/unit/test_storage_adapters.py`
- `tests/integration/test_api.py`

## Acceptance criteria
- `uv run ruff check src tests scripts` passes.
- `uv run ruff format --check src tests scripts` passes.
- `uv run mypy src` passes.
- `uv run pytest tests/unit/test_fake_llm_adapter.py tests/unit/test_storage_adapters.py tests/integration/test_api.py tests/unit/test_claude_adapter.py tests/unit/test_openai_adapter.py tests/unit/test_kimi_adapter.py` passes.
- `StorageAdapterFactory.create` contains no `if adapter_cls is FileSystemStorageAdapter` branch.
- `main.py` still compiles (do not break its existing calls to `StorageAdapterFactory().create`; the integration wave will switch to `SearchToolFactory`).
- `routes.py` no longer instantiates `BriefMarkdownRenderer()` directly.

## Notes / conflict avoidance
- Do **not** change `src/brief_scout/main.py`. Create the factories and dependencies so the integration wave can swap the hard-coded search branch and wire the renderer in one place.
- Do **not** change `src/brief_scout/application/services/` unless an import breaks because Agent 1 deletes `template_renderer.py`. In that case, import from `brief_scout.infrastructure.template` instead.
