# Agent Guide — Brief Scout

This file contains agent-focused guidance for working on the Brief Scout codebase.

## Architecture

- **Ports & Adapters (Hexagonal/Clean)** with Protocol-based ports.
- Domain models in `src/brief_scout/domain/models/`.
- Application use cases in `src/brief_scout/application/use_cases/`.
- Infrastructure adapters in `src/brief_scout/infrastructure/`.
- FastAPI interface in `src/brief_scout/interfaces/api/`.

## How to change the intake interview

The conversational intake flow is driven by the declarative schema in
`config/journey.yaml`. To add, remove, or reorder a field:

1. **Add the field to `IntakeData`** in `src/brief_scout/domain/models/intake.py`
   so it can be persisted.

2. **Add a `JourneyField` entry** to `config/journey.yaml`:

   ```yaml
   - name: industry
     type: string
     required: true
     ask_when_missing: true
     question_template: "What industry is {{brand_name}} in?"
     acknowledgement_template: "Industry: {{industry}}."
   ```

   Supported types: `string`, `list`, `object`. For `object` fields, declare
   `properties` for the sub-fields that should be merged.

3. **If the field is part of the demo**, add its value to the appropriate turn
   in `tests/fixtures/demo_journey.yaml`.

That is usually all that is required. The `CompletenessChecker`,
`IntakeDataMerger`, question selection, and extraction prompt schema are all
derived from `config/journey.yaml`.

## Quality gates

Always run before committing:

```bash
uv run pytest tests/ -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
```

Coverage threshold is configured at 85%.

## Running the demo

```bash
uv run python scripts/run_demo.py
```

This writes a transcript to `demo_conversation.md`.

## How to add a research step

Research steps are now pluggable. To add a new research dimension:

1. Create a class implementing `ResearchStep` in
   `src/brief_scout/application/services/research_steps/`:

   ```python
   from pydantic import BaseModel
   from brief_scout.application.services.research_pipeline import ResearchStep

   class MarketSizingResult(BaseModel):
       tam: str = ""

   class MarketSizingStep(ResearchStep):
       name = "market_sizing"

       async def execute(self, intake_data: IntakeData) -> BaseModel:
           ...
           return MarketSizingResult(tam="...")
   ```

2. Add a prompt template under `prompts.research_steps` in `config/default.yaml`:

   ```yaml
   prompts:
     research_steps:
       market_sizing:
         system: "..."
         user: "..."
   ```

3. The `ResearchUseCase` builds the pipeline from the configured steps automatically;
   no use-case code changes are required.

## How to add a field type

Field-type merge behavior is extensible via `FieldTypeRegistry`.
To support a new type such as `number`:

```python
from brief_scout.domain.services.field_type_registry import FieldTypeRegistry

def merge_number(existing: float, extracted: float) -> float:
    return extracted if extracted != 0 else existing

registry = create_default_registry()
registry.register("number", merge_number)
merger = IntakeDataMerger(journey=journey, registry=registry)
```

## Narrow ports

Application services declare narrow dependencies in
`src/brief_scout/domain/ports/application_ports.py` (e.g., `LoggerPort`,
`SessionWriter`, `StructuredCompletionPort`, `TemplateRenderer`). Prefer
injecting these small interfaces over the full `TelemetryPort`,
`BriefStoragePort`, or `LLMPort` when only a subset is needed.
