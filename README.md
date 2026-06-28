# Brief Scout

> Conversational creative brief generation powered by AI research.

Brief Scout is a conversational brief intake + research agent. A user chats through 5-7 natural questions. The system extracts structured data, fires 5 parallel LLM research calls, and synthesizes everything into a fully populated creative brief in under 2 minutes.

## Architecture

```
Interfaces (FastAPI, WebSocket, CLI)
Application (Use Cases, DTOs, Orchestration)
Domain (Entities, Value Objects, Ports)
Infrastructure (LLM Adapters, Config, Telemetry, Storage)
```

**Ports and Adapters (Hexagonal/Clean Architecture)** — Dependencies point inward only. All external concerns (LLM, storage, telemetry) are abstracted behind Protocol-based ports with swappable adapters.

### System Flow

```
[User Chat] -> [Intake Use Case] -> [Structured JSON Extraction]
                                            |
                                    [Completeness Check]
                                            |
                        [Research Use Case -- 5 Parallel Calls]
                            |- Brand Audit
                            |- Competitor Ad Scan
                            |- Category & Trend Pulse
                            |- Customer Voice
                            |- Hook & Angle Mining
                                            |
                            [Research Results Aggregation]
                                            |
                        [Synthesis Use Case -> Brief]
                                            |
                                [Render Brief to User]
```

## Quick Start

### Prerequisites

- Python 3.11+
- pip or uv

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd brief_scout

# Install dependencies
pip install -e ".[dev]"

# Or with uv
uv pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=brief_scout --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_domain_models.py -v

# Run integration tests
pytest tests/integration/ -v
```

### Running the Server

```bash
# Development mode (with file system storage + DEBUG logging)
BRIEF_SCOUT_ENV=development uvicorn brief_scout.interfaces.api.routes:app --reload

# Production mode (in-memory storage + INFO logging)
BRIEF_SCOUT_ENV=default uvicorn brief_scout.interfaces.api.routes:app
```

## API Documentation

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat/sessions` | Create a new chat session |
| `POST` | `/chat/{session_id}/message` | Send a message, get assistant response |
| `GET`  | `/chat/{session_id}/stream` | SSE stream for real-time progress |
| `GET`  | `/briefs/{session_id}` | Retrieve a generated brief |
| `GET`  | `/health` | Health check |

### Example: Create Session

```bash
curl -X POST http://localhost:8000/chat/sessions
```

Response:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "intaking",
  "created_at": "2026-06-27T12:00:00"
}
```

### Example: Send Message

```bash
curl -X POST http://localhost:8000/chat/550e8400-e29b-41d4-a716-446655440000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "We are building creative for Nike"}'
```

### Example: Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "providers": ["fake"]
}
```

## Configuration Guide

Configuration is loaded from YAML files in the `config/` directory. Environment-specific overlays are supported.

### Configuration Files

| File | Purpose |
|------|---------|
| `config/default.yaml` | Base configuration (all prompts, thresholds) |
| `config/development.yaml` | Development overrides (DEBUG logging, file system storage) |

### Environment Selection

Set `BRIEF_SCOUT_ENV` to select the configuration overlay:

```bash
# Use default.yaml only
export BRIEF_SCOUT_ENV=default

# Use default.yaml + development.yaml
export BRIEF_SCOUT_ENV=development
```

### Key Configuration Sections

#### Prompts

All LLM prompts are defined as Jinja2 templates:

```yaml
prompts:
  intake_system: |
    You are a creative strategist onboarding a new user...

  research_brand_audit:
    system: "You are a creative analyst. Return ONLY JSON."
    user: "Research the brand: {{brand_name}}..."
```

#### LLM Providers

```yaml
llm_providers:
  fake:
    adapter_class: "brief_scout.infrastructure.llm.fake_llm_adapter.FakeLLMAdapter"
    fixture_dir: "tests/fixtures/llm_responses"
    latency_ms: 50
```

#### Telemetry

```yaml
telemetry:
  adapter: local_file      # Options: local_file, opentelemetry
  log_level: INFO
  log_dir: "./logs"
```

#### Storage

```yaml
storage_adapter: in_memory  # Options: in_memory, file_system
```

## Domain Models

### Intake Data

| Field | Type | Required |
|-------|------|----------|
| `brand_name` | `str` | Yes |
| `brand_url` | `str` | No |
| `competitors` | `list[str]` | Yes (>=1) |
| `primary_goal` | `str` | Yes |
| `target_customer` | `str` | Yes |
| `creative_directions` | `CreativeDirections` | No |
| `additional_context` | `str` | No |

### Research Results (5 parallel calls)

| Call | Output Model | Key Fields |
|------|-------------|------------|
| Brand Audit | `BrandAuditResult` | positioning, creative angle, key messages, recent campaigns |
| Competitor Scan | `CompetitorScanResult` | competitors, patterns, whitespace opportunities |
| Trend Pulse | `TrendPulseResult` | category trends, cultural moments, emerging angles |
| Customer Voice | `CustomerVoiceResult` | language, desires, frustrations, objections |
| Hook Mining | `HookMiningResult` | hook types, emotional/rational angles, headlines |

### Brief (Final Output)

The `Brief` model is the primary deliverable — a structured creative brief with:

- Brand positioning and goals
- Target customer profile
- Desires and objections
- Competitive landscape
- 3 recommended creative angles with rationale
- Proven hook types and sample headlines
- Creative mandatories (explore/avoid)
- Category trends

Render to markdown via `brief.to_markdown()`.

## FakeLLMAdapter — Fixture System

The primary LLM adapter for development and testing uses JSON fixture files:

```
tests/fixtures/llm_responses/
├── brand_audit/nike.json          # Brand audit for Nike
├── competitor_scan/nike_vs_adidas_puma.json
├── customer_voice/nike_customers.json
├── hook_mining/nike_hooks.json
├── trend_pulse/nike_trends_2026.json
├── synthesis/nike_brief.json      # Complete brief
└── default/default.json           # Fallback
```

Each fixture contains:

```json
{
    "_meta": {
        "description": "...",
        "match_keywords": ["nike", "brand audit"],
        "latency_ms": 100
    },
    "response": { ... }
}
```

## Project Structure

```
brief_scout/
├── .cursorrules                        # AI dev context
├── README.md                           # This file
├── pyproject.toml                      # Dependencies + project config
├── config/
│   ├── default.yaml                    # Default configuration
│   └── development.yaml                # Dev overrides
├── src/brief_scout/
│   ├── __init__.py
│   ├── domain/
│   │   ├── models/                     # IntakeData, Brief, ResearchBundle
│   │   ├── ports/                      # LLMPort, TelemetryPort, StoragePort
│   │   └── services/                   # CompletenessChecker
│   ├── application/
│   │   ├── dto/                        # MessageRequest, ChatResponse
│   │   └── use_cases/                  # Intake, Research, Synthesis
│   ├── infrastructure/
│   │   ├── llm/                        # FakeLLMAdapter
│   │   ├── config/                     # YAMLConfigAdapter
│   │   ├── telemetry/                  # LocalFileTelemetryAdapter
│   │   └── storage/                    # InMemoryStorageAdapter
│   ├── interfaces/api/                 # FastAPI routes
│   └── config/schemas/                 # Pydantic config schemas
└── tests/
    ├── conftest.py                     # Shared fixtures
    ├── unit/                           # Unit tests
    └── integration/                    # E2E tests
```

## License

MIT
