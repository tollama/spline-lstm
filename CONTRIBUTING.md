# Contributing to spline-lstm

Thank you for your interest in contributing to spline-lstm! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.10 or 3.11 (3.12 not yet supported due to TensorFlow)
- Node.js 18+ (for UI development)
- Git

### Getting Started

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/spline-lstm.git
   cd spline-lstm
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -e ".[dev,backend]"
   pre-commit install
   ```

4. **Install UI dependencies** (optional, for UI work)
   ```bash
   cd ui && npm install
   ```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run quick smoke test
make smoke-gate
```

## Code Style

We use the following tools to maintain code quality:

- **Ruff** for linting and formatting
- **Mypy** for type checking
- **Pre-commit hooks** for automated checks

```bash
# Format code
ruff format src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/
```

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clear, descriptive commit messages
   - Add tests for new functionality
   - Update documentation as needed

3. **Run the CI gate locally**
   ```bash
   make ci-gate
   ```

4. **Push and create a PR**
   - Push your branch to your fork
   - Open a Pull Request against the `main` branch
   - Fill out the PR template completely
   - Link any relevant issues

5. **Code review**
   - Address review feedback promptly
   - Keep discussion constructive and focused

## Commit Message Guidelines

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters
- Reference issues and pull requests liberally after the first line

Example:
```
Add support for custom spline degrees

- Allow users to specify spline degree per feature
- Add validation for degree values (1-5)
- Update docs with new parameter

Closes #123
```

## Reporting Issues

- Use the GitHub issue tracker
- Use the appropriate issue template (bug report or feature request)
- Provide as much context as possible

## Questions?

Feel free to open an issue with the "question" label for any clarification.

Thank you for contributing!