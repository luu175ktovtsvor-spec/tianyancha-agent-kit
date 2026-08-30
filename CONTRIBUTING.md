# Contributing

Contributions are welcome when they keep the workflow reusable and verifiable.

## Before opening a pull request

1. Use fictional fixtures; keep task-specific materials outside the public
   repository.
2. Keep source-specific parsing in an adapter and keep filtering rules in a
   profile. Do not embed a private industry standard in package defaults.
3. Add tests for behavior changes and run:

   ```bash
   python -m pytest
   tyc-agent audit-public --path .
   ```

4. Explain the user-visible behavior in the pull request.

Security issues are described in [SECURITY.md](SECURITY.md).
