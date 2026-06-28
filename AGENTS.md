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
