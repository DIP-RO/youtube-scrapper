# Contributing to yt-network-scraper

Thank you for your interest in contributing! This document outlines the process for contributing to the project.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/yt-network-scraper.git
   cd yt-network-scraper
   ```
3. Create a virtual environment and install development dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
4. Create a branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Running Tests

```bash
pytest
```

All tests use mocked HTTP responses and mocked Selenium drivers. Do not add tests that make live YouTube requests to the default test suite. If you need integration tests, mark them separately.

### Code Style

- Follow PEP 8
- Use type hints on all public functions
- Use `logging` instead of `print` for diagnostic output
- Keep functions small and focused
- Add or update tests for any changes to parsing or network logic

### Commit Messages

Use clear, descriptive commit messages:

```
Add support for transcript language fallback

When the preferred language track is unavailable, fall back to
the first available track instead of returning no transcript.
```

### Pull Request Process

1. Ensure all tests pass: `pytest`
2. Ensure the package builds: `python -m build`
3. Ensure the build is valid: `twine check dist/*`
4. Update the CHANGELOG.md if applicable
5. Open a pull request with a clear description of the changes

## Reporting Issues

- Use GitHub Issues to report bugs or request features
- Include the Python version, OS, and package version
- For bugs, include a minimal reproduction case
- Do not include YouTube URLs to private or sensitive videos

## Security

If you discover a security vulnerability, please see [SECURITY.md](SECURITY.md) for reporting instructions. Do not open a public issue for security vulnerabilities.

## Code of Conduct

Be respectful and constructive. Harassment and discrimination are not tolerated.
