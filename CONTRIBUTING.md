# 🤝 Contributing to LUISA

Thank you for your interest in contributing to LUISA! This document provides guidelines for contributing to the project.

---

## 📋 Table of Contents
1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Coding Standards](#coding-standards)
5. [Testing](#testing)
6. [Pull Request Process](#pull-request-process)
7. [Reporting Bugs](#reporting-bugs)
8. [Suggesting Features](#suggesting-features)

---

## 📜 Code of Conduct

### Our Standards
- Be respectful and inclusive
- Accept constructive criticism
- Focus on what's best for the community
- Show empathy towards others

### Enforcement
Violations can be reported to [Your Email]. All complaints will be reviewed and investigated.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Git
- Basic knowledge of FastAPI and AI/LLM concepts

### Setup Development Environment

1. **Fork and Clone**
```bash
git clone https://github.com/YOUR_USERNAME/luisa.git
cd luisa
```

2. **Create Virtual Environment**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # If exists
```

4. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your test credentials
```

5. **Initialize Database**
```bash
python scripts/init_db.py
```

6. **Run Tests**
```bash
pytest tests/
```

7. **Start Development Server**
```bash
python main.py
```

---

## 🔄 Development Workflow

### Branching Strategy
- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/your-feature-name` - New features
- `fix/bug-description` - Bug fixes
- `hotfix/critical-issue` - Critical production fixes

### Creating a Branch
```bash
git checkout -b feature/add-new-intent
```

### Making Changes
1. Write code following [Coding Standards](#coding-standards)
2. Add tests for new functionality
3. Run tests: `pytest tests/`
4. Update documentation if needed

### Committing
Use conventional commit messages:
```bash
git commit -m "feat: add support for product comparison intent"
git commit -m "fix: resolve cache invalidation issue"
git commit -m "docs: update deployment guide"
git commit -m "test: add tests for OpenAI gating"
```

**Commit Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

---

## 📏 Coding Standards

### Python Style
- Follow **PEP 8**
- Use **type hints** for function signatures
- Maximum line length: **100 characters**
- Use **docstrings** for classes and functions

Example:
```python
def classify_message_type(text: str) -> MessageType:
    """
    Classifies a user message into one of four types.
    
    Args:
        text: The user's message text
        
    Returns:
        MessageType enum indicating the classification
    """
    # Implementation...
```

### Code Organization
- Keep functions small and focused (single responsibility)
- Use descriptive variable names
- Avoid magic numbers (use constants)
- Group related imports

### Formatting Tools (Optional but Recommended)
```bash
# Install formatters
pip install black ruff

# Format code
black backend/app/
ruff check backend/app/ --fix
```

---

## 🧪 Testing

### Running Tests
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_conversation_smoke.py

# Run specific test
pytest tests/test_conversation_smoke.py::test_clasificacion_mensaje_programacion
```

### Writing Tests
- Place tests in `backend/tests/`
- Name test files: `test_*.py`
- Name test functions: `test_*`
- Use descriptive test names

Example:
```python
def test_gating_openai_blocked_for_non_business():
    """Ensure OpenAI is not called for programming questions."""
    text = "cómo hago un for en python"
    message_type = classify_message_type(text)
    
    assert message_type == MessageType.NON_BUSINESS
    # Verify OpenAI is not called
```

### Test Coverage
- Aim for **>80% coverage** for new code
- Test critical paths (OpenAI gating, handoffs, guardrails)
- Test edge cases and error handling

---

## 🔀 Pull Request Process

### Before Submitting
1. ✅ Tests pass: `pytest tests/`
2. ✅ Code formatted (if using black/ruff)
3. ✅ No secrets committed
4. ✅ Documentation updated
5. ✅ Commit messages follow convention

### Submitting PR
1. Push your branch:
```bash
git push origin feature/your-feature-name
```

2. Open a Pull Request on GitHub with:
   - **Clear title**: `feat: add intent for warranty questions`
   - **Description**: What does this PR do? Why?
   - **Related issues**: Fixes #123
   - **Testing**: How did you test this?
   - **Screenshots**: If UI changes

### PR Template
```markdown
## 🎯 Description
Brief description of changes.

## 🔗 Related Issues
Fixes #123

## 🧪 Testing
- [ ] Unit tests added/updated
- [ ] Manual testing performed
- [ ] All tests pass

## 📸 Screenshots (if applicable)

## ✅ Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No secrets committed
```

### Review Process
- Maintainers will review within **48 hours**
- Address feedback promptly
- Once approved, maintainers will merge

---

## 🐛 Reporting Bugs

### Before Reporting
- Search existing issues
- Verify it's reproducible
- Collect relevant logs (sanitize secrets!)

### Report Using GitHub Issues
Use the **Bug Report** template and include:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version)
- Logs (sanitized)

---

## 💡 Suggesting Features

### Before Suggesting
- Search existing feature requests
- Consider if it aligns with project goals

### Suggest Using GitHub Issues
Use the **Feature Request** template and include:
- Problem description
- Proposed solution
- Use case
- Alternatives considered

---

## 🏗️ Project Structure

```
AI-Agents/Sastre/
├── backend/
│   ├── app/
│   │   ├── models/          # Database models
│   │   ├── rules/           # Business rules & guardrails
│   │   ├── services/        # Core business logic
│   │   ├── routers/         # API endpoints
│   │   └── prompts/         # OpenAI prompts
│   ├── tests/               # Test suite
│   ├── scripts/             # Utility scripts
│   └── main.py              # Legacy entrypoint
├── frontend/
│   └── index.html           # Demo UI
├── .env.example             # Environment template
├── .gitignore
├── README.md
├── DEPLOYMENT.md
├── SECURITY.md
└── CONTRIBUTING.md
```

---

## 🔐 Security

**Do not** commit:
- API keys
- Passwords
- Private keys
- `.env` files

If you find a security vulnerability, **do not** open a public issue. Email [Your Security Email] instead.

---

## 📞 Contact

- **Maintainer**: [Your Name]
- **Email**: [Your Email]
- **Issues**: https://github.com/YOUR_USERNAME/luisa/issues

---

## 🎉 Recognition

Contributors will be acknowledged in:
- `CONTRIBUTORS.md` (if we create it)
- GitHub contributors page
- Release notes

Thank you for contributing to LUISA! 🚀
