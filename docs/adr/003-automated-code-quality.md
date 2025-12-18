# ADR 003: Automated Code Quality in CI/CD

## Status
Accepted

## Context
For a Tech Lead portfolio, demonstrating advanced DevOps practices is crucial. Manual code review is time-consuming and inconsistent. Automated code quality checks ensure:
1. **Consistency**: Every commit is reviewed with the same standards
2. **Security**: Vulnerabilities are caught before deployment
3. **Maintainability**: Code style is enforced automatically

## Decision
We implement a **Code Quality workflow** in GitHub Actions that runs on every PR and push:
- **Linting (Flake8)**: Catches Python syntax errors and code smells
- **Formatting (Black)**: Ensures consistent code style
- **Security (Bandit)**: Scans for common security vulnerabilities
- **Dependency Check (Safety)**: Identifies vulnerable dependencies
- **PR Comments**: Automated feedback on pull requests

## Consequences

### Positive
- **Interview Impact**: Shows understanding of modern DevOps practices
- **Code Quality**: Maintains high standards automatically
- **Security**: Catches vulnerabilities before they reach production
- **Documentation**: Security reports are saved as artifacts

### Negative
- **Build Time**: Adds ~2-3 minutes to CI pipeline
- **False Positives**: May flag non-issues (mitigated by configuration)

## Alternatives Rejected
- **SonarQube**: Too heavy for a portfolio project
- **Manual Review Only**: Not scalable, inconsistent

## Implementation
- Workflow: `.github/workflows/code-quality.yml`
- Runs on: Pull requests and pushes to main
- Tools: flake8, black, bandit, safety
