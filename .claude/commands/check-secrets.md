---
description: Scan the working tree and git history for committed secrets
---
Search the repo for likely secrets: strings starting with gsk_, sk-, AIza, hf_, ghp_, xox, a Bearer token, private key headers, and any non empty value in an .env file. Search git history for the same patterns. Never print a full secret; show file, line and the first 4 characters. Confirm .env is gitignored and .env.example has only empty values. Report PASS or the list of findings.
