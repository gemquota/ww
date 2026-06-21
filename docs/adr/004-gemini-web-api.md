# ADR-004: Gemini Web API Choice

**Status**: Accepted
**Date**: 2025-02-10

## Context

The bridge needs an LLM backend. Options include:

1. Google Gemini Web API (free, cookie-based)
2. Google Gemini Official API (paid, API key)
3. OpenAI API (paid)
4. Anthropic API (paid)
5. Local models (free, slower)

## Decision

Use `gemini-webapi` library as the primary backend, with the `google-genai`
SDK as an alternative for API key users. The Gemini Web API provides free
access to Gemini models without requiring a credit card.

Key factors:
- **Cost**: Free tier is attractive for hobbyists and evaluation
- **Capability**: Gemini competes well with GPT-4 for coding tasks
- **Speed**: Competitive with paid alternatives
- **Ecosystem**: Growing Python library support

## Consequences

**Positive**:
- Zero-cost entry for users
- No credit card required
- Competitive model quality

**Negative**:
- Cookie auth is fragile (expires, requires browser)
- Web API may change without notice
- No SLA compared to paid API
- Free tier has rate limits (~10 RPM)

## Alternatives Considered

1. **OpenAI API**: Better documentation, but costs money
2. **Anthropic API**: Excellent coding benchmarks, but most expensive
3. **Local models (llama.cpp)**: Free and private, but much slower
