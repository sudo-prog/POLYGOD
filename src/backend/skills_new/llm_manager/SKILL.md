# llm_manager.skill

> LLM Provider Manager Skill for POLYGOD

Manages LLM providers via LiteLLM - monitors health, usage, costs, and allows dynamic provider switching.

## Overview

This skill manages all LLM connections through `LLMConcierge` in `src/backend/services/llm_concierge.py`.

## Capabilities

1. **List Providers** - Show all configured LLM providers with health status
2. **Daily Usage** - Show token usage per provider (from database)
3. **Switch Default** - Change the default provider at runtime
4. **Detect Paid/Free** - Warn when using paid providers vs free ones
5. **Add Provider** - Register new providers without restart

## Supported Providers

### Free (No Credit Card Required)
| Provider | Model | Notes |
|----------|-------|-------|
| Groq | llama-3.3-70b-versatile | Completely free, fast |
| Groq | llama-3.1-405b-reasoning | Free reasoning model |
| Google | gemini-2.5-flash-lite | Generous free tier |
| OpenRouter | deepseek-r1 | Has free tier credits |

### Free (With Setup)
| Provider | Model | Notes |
|----------|-------|-------|
| Ollama | llama3.1:8b | Run locally, no internet |
| Ollama | codellama:7b | Local code assistant |

### Paid (Avoid by Default)
| Provider | Model | Est. Cost |
|----------|-------|----------|
| OpenAI | gpt-4o | ~$3/1M tokens |
| Anthropic | claude-sonnet | ~$3/1M tokens |

## Usage

### List All Providers
```
Show me all configured LLM providers.
```

### Check Usage Today
```
How many tokens did we use today?
```

### Switch Default Provider
```
Switch to Groq as the default.
```

### Add New Provider
```
Add Ollama running on localhost:11434
```

### Check Costs
```
Which providers are paid vs free?
```

## Implementation

- **Service**: `LLMConcierge` in `services/llm_concierge.py`
- **Models**: `Provider`, `UsageLog` in `models/llm.py`
- **Metrics**: Prometheus at `/metrics`

## Files Modified

- `services/llm_concierge.py` - Main concierge logic
- `config.py` - Add new provider env vars
- `.env` - Provider API keys

## Validation

Run validation:
```bash
uv run python -c "from src.backend.services.llm_concierge import concierge; print(concierge.get_security_status())"
```

## Notes

- All calls fallback automatically if primary provider fails
- Health checks run every 30 minutes via APScheduler
- Token usage tracked in `usage_logs` table
- Ollama requires local installation: https://ollama.com
