# ADR-010: Keep URL fetching disabled

**Status:** Accepted  
**Date:** 2026-11-20

## Context

The former URL fetch tool did not provide sufficiently robust DNS pinning, redirect revalidation and private-address/SSRF protections.

## Decision

Do not register or expose URL fetching in the supported runtime until DNS resolution is pinned to validated addresses and every redirect is independently validated.

## Consequences

- URL fetch requests from the model fail closed as unknown/unavailable tools.
- The browser direct-tool API remains read-only and does not expose network fetch.
- Re-enable only with focused DNS rebinding, redirect, IPv4/IPv6 and private-address regression tests.
