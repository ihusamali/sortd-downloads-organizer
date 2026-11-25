# Contributing

Thanks for helping improve sortd. Keep changes focused, local-first, and reversible. Add or update tests for behavior changes, run the commands below, and describe platform impact in your pull request.

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy src/
pytest -v --cov=sortd
```

Please avoid logging document contents, keep provider calls opt-in, and do not perform destructive operations without a clear configuration setting.
