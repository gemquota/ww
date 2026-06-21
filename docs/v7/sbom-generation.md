# SBOM Generation — V7-12#3

## Purpose
Generate Software Bill of Materials (SBOM) for WW Bridge.

## Format
SPDX 2.3 specification including package names, versions, and licenses.

## Generation
```bash
python .tel/scripts/dependency_auditor.py --sbom
```