# Argus engine

This directory contains the Python analysis engine. It is an initial scaffold;
scanning and triage are not implemented yet.

## Development

Install Python 3.13 or newer and [uv](https://docs.astral.sh/uv/), then run
these commands from this directory:

```sh
uv sync
uv run ruff check .
uv run mypy argus
uv run pytest
```

The test directory is currently empty, so pytest reports that no tests were
collected until engine tests are added. The project is run from this directory;
it is not yet configured as an installable package or command-line tool.
