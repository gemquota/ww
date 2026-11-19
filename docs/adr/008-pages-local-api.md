# ADR-008: Static Pages client with device-hosted API

**Status:** Accepted  
**Date:** 2026-11-20

## Context

The browser UI should be deployable without moving Gemini credentials or workspace files to a hosted service.

## Decision

Publish `src/dashboard/chat.html` as a static GitHub Pages site. Run FastAPI locally on the user's device and connect the page to that API. The API binds to loopback by default and requires an API key for protected routes.

## Consequences

- The Pages artifact contains no Gemini credentials or backend secrets.
- Browser sessions, API authentication, tool execution and approval remain in the local backend.
- Remote browser access requires a private HTTPS tunnel/VPN and explicit CORS origins.
- The API key is held in tab sessionStorage; browser transcripts are localStorage data.
- There is one authoritative Pages workflow; the old progress-dashboard deploy workflow is retired.
