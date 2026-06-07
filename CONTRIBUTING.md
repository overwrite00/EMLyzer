# 🎯 Contributing to EMLyzer

Thank you for your interest in contributing to EMLyzer! We welcome bug reports, feature requests, documentation improvements, and code contributions from the community.

---

## 🎯 Welcome

EMLyzer is an open-source email threat analysis platform. Whether you're fixing a bug, improving documentation, adding a new analyzer, or enhancing the reputation system, your contributions make EMLyzer better for everyone.

Before contributing, please review this guide and our [Code of Conduct](./CODE_OF_CONDUCT.md).

---

## 🔀 Branch Strategy

- **Main branch**: `main` (protected, production-ready)
- **Development branch**: `develop` (main integration branch, PRs target here)
- **Feature branches**: Create from `develop`, e.g., `feature/url-analyzer-improvements`

### Submitting Code

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Create a feature branch** from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```
4. **Make your changes** and test thoroughly
5. **Commit** with clear messages (see [Code Standards](#code-standards))
6. **Push** to your fork
7. **Create a Pull Request** targeting `develop` (NOT `main`)

> ⚠️ PRs to `main` will be rejected. Always target `develop`.

---

## 🛠️ Development Setup

### Prerequisites

- **Python**: 3.11, 3.12, or 3.13 (see [REQUIREMENTS.md](./docs/REQUIREMENTS.md))
- **Node.js**: 18+ (for frontend)
- **Git**

### Backend Setup

```bash
# Clone and enter directory
git clone https://github.com/YOUR-USERNAME/EMLyzer.git
cd EMLyzer

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# (Optional) Install NLP dependencies
pip install -r backend/requirements_optional.txt
```

### Frontend Setup

```bash
cd frontend
npm install
```

### Starting the Application

```bash
# From project root

# Windows:
./start.bat

# macOS/Linux:
./start.sh
```

The application will be available at **http://localhost:8000**.

---

## 📝 Code Standards

### Type Hints

All Python code must include type hints:

```python
def analyze_email(file_path: str, include_reputation: bool = False) -> dict[str, Any]:
    """Analyze an email file and return results."""
    pass
```

### Docstrings

Use Google-style docstrings:

```python
def compute_risk_score(indicators: dict[str, Any]) -> float:
    """Compute normalized risk score from analysis indicators.
    
    Args:
        indicators: Dictionary containing header, body, url, and attachment indicators.
    
    Returns:
        Risk score between 0 and 100.
    
    Raises:
        ValueError: If indicators dict is empty.
    """
    pass
```

### Commit Message Format

Follow the conventional commits format:

```
type(scope): description

[optional body]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
**Scope**: `api`, `core`, `nlp`, `ui`, `deps`, etc.

**Examples**:
- `feat(url-analyzer): add IP reputation check`
- `fix(header-analysis): correct SPF validation logic`
- `docs(readme): update installation instructions`
- `test(core): add 5 new attachment analysis tests`

---

## ✅ Testing

### Running Tests

All backend changes must pass the test suite:

```bash
# From project root
./run_tests.sh     # macOS/Linux
./run_tests.bat    # Windows
```

Or directly:

```bash
cd backend
pytest tests/test_core.py -v
```

### Test Requirements

- **Minimum coverage**: All new features must include tests
- **All tests must pass**: No regressions allowed
- **Test count**: Currently 119 tests — aim to maintain or increase this

### Writing Tests

Place tests in `backend/tests/test_core.py`:

```python
@pytest.mark.asyncio
async def test_header_analysis_with_spoofed_from():
    """Test detection of From field spoofing."""
    email = create_test_email(from_header="Amazon <account@suspicious-domain.com>")
    result = await analyze_headers(email)
    assert result.risk_score >= 20
    assert any(f.severity == "HIGH" for f in result.findings)
```

---

## 📤 Submitting a Pull Request

### PR Description Template

```markdown
## Summary
Brief description of changes

## Related Issue
Fixes #(issue number) or Relates to #(issue number)

## Type of Change
- [ ] Bug fix (non-breaking)
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Added tests for new functionality
- [ ] All tests pass locally
- [ ] Tested on Windows/macOS/Linux (if applicable)

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] CHANGELOG.md updated (if user-facing change)
```

### PR Guidelines

- **Keep PRs focused** — One feature or bug fix per PR
- **Reference related issues** — Use `Fixes #123` to link issues
- **Describe changes clearly** — Help reviewers understand your approach
- **Be responsive** — Address feedback promptly
- **Don't force-push** — Makes reviewing history difficult

---

## 🔧 Dependency Updates

### Automated Updates (Dependabot)

We use Dependabot to automate dependency updates:

- **Minor & patch updates** → Automatically merged if tests pass
- **Major version updates** → Require manual review and approval

### Manual Updates

To update dependencies manually:

```bash
# Backend
pip list --outdated
pip install --upgrade package_name
pip freeze > backend/requirements.txt

# Frontend
npm outdated
npm update package_name
```

Then test thoroughly before committing:

```bash
./run_tests.sh
npm run build
```

---

## ❓ Questions?

- **Documentation**: Check [docs/](./docs/) folder
- **Usage Questions**: [GitHub Discussions](https://github.com/overwrite00/EMLyzer/discussions)
- **Bugs**: [GitHub Issues](https://github.com/overwrite00/EMLyzer/issues)
- **Security**: See [SECURITY.md](./SECURITY.md)

---

## 🙏 Thank You

Thank you for contributing to EMLyzer! Your efforts help make email security analysis more accessible and effective for everyone.

---

*Last updated: 2026-06-07*
*← [Code of Conduct](./CODE_OF_CONDUCT.md) | [Security →](./SECURITY.md)*
