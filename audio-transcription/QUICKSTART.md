# Audio Transcription - Quick Start Guide

Get up and running with the audio-transcription component in 5 minutes.

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Git
- AWS account (for deployment only)

## Step 1: Clone and Navigate

```bash
# If you haven't cloned the repository
git clone https://github.com/your-org/low-latency-translate.git
cd low-latency-translate/audio-transcription
```

## Step 2: Install Dependencies

```bash
# Install production and development dependencies
make install

# Or manually
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**Expected output:**
```
Successfully installed boto3-1.28.0 librosa-0.10.0 pytest-7.4.0 ...
```

## Step 3: Run Tests

```bash
# Run all tests with coverage
make test
```

**Expected output:**
```
======================== 109 passed in 10.54s ========================
Coverage: 87%
```

## Step 4: Verify Installation

```bash
# Check that imports work
python -c "from shared.models import PartialResult; print('✓ Models OK')"
python -c "from shared.services import DeduplicationCache; print('✓ Services OK')"
python -c "from shared.utils import normalize_text; print('✓ Utils OK')"
```

**Expected output:**
```
✓ Models OK
✓ Services OK
✓ Utils OK
```

## Step 5: Explore the Code

### Try the Text Normalization

```python
from shared.utils import normalize_text, hash_text

# Normalize text
text = "Hello, World!"
normalized = normalize_text(text)
print(f"Normalized: '{normalized}'")  # Output: 'hello world'

# Generate hash
hash_value = hash_text(text)
print(f"Hash: {hash_value[:16]}...")  # Output: SHA-256 hash
```

### Try the Deduplication Cache

```python
from shared.services import DeduplicationCache

# Create cache with 10-second TTL
cache = DeduplicationCache(ttl_seconds=10)

# Add text
cache.add("Hello everyone!")

# Check if exists (case-insensitive, punctuation-agnostic)
print(cache.contains("hello everyone"))  # True
print(cache.contains("HELLO EVERYONE"))  # True
print(cache.contains("hello, everyone!"))  # True
```

### Try the Result Buffer

```python
import time
from shared.models import PartialResult
from shared.services import ResultBuffer

# Create buffer
buffer = ResultBuffer(max_capacity_seconds=10)

# Add partial result
result = PartialResult(
    result_id='test-123',
    text='hello world',
    stability_score=0.92,
    timestamp=time.time(),
    session_id='session-456'
)

buffer.add(result)
print(f"Buffer size: {buffer.size()}")  # Output: 1

# Get result
retrieved = buffer.get_by_id('test-123')
print(f"Retrieved: {retrieved.text}")  # Output: hello world
```

## Development Workflow

### 1. Make Changes

Edit files in `shared/` directory:
- `shared/models/` - Data models
- `shared/services/` - Business logic
- `shared/utils/` - Utilities

### 2. Write Tests

Add tests in `tests/unit/`:
```python
# tests/unit/test_my_feature.py
def test_my_feature():
    # Arrange
    ...
    # Act
    ...
    # Assert
    assert result == expected
```

### 3. Run Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/test_my_feature.py -v

# Run with coverage report
pytest --cov=shared --cov-report=html
```

### 4. Format and Lint

```bash
# Format code
make format

# Run linters
make lint
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat(audio-transcription): add my feature"
git push
```

## Common Commands

```bash
# Install dependencies
make install

# Run all tests
make test

# Format code (Black)
make format

# Run linters (pylint, flake8, mypy)
make lint

# Clean build artifacts
make clean

# Deploy to dev environment (requires AWS setup)
make deploy-dev
```

## Project Structure Quick Reference

```
audio-transcription/
├── shared/              # Production code
│   ├── models/         # Data models
│   ├── services/       # Business logic
│   └── utils/          # Utilities
├── tests/              # All tests
│   └── unit/          # Unit tests
├── docs/              # Task summaries
└── README.md          # Full documentation
```

## Running Specific Tests

```bash
# Run tests for a specific module
pytest tests/unit/test_data_models.py -v

# Run tests matching a pattern
pytest -k "test_normalize" -v

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=shared --cov-report=term-missing
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'shared'`

**Solution**: Make sure you're in the `audio-transcription` directory and have installed dependencies:
```bash
cd audio-transcription
pip install -e .
```

### Test Failures

**Problem**: Tests fail with coverage errors

**Solution**: Run tests from the component root:
```bash
cd audio-transcription
pytest tests/unit/ -v
```

### Dependency Issues

**Problem**: `ImportError: cannot import name 'librosa'`

**Solution**: Reinstall dependencies:
```bash
pip install -r requirements.txt --force-reinstall
```

## Next Steps

### Learn More
- Read [README.md](README.md) for technical architecture
- Check [OVERVIEW.md](OVERVIEW.md) for current status
- Review [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for file organization

### Start Developing
- Review task summaries in `docs/TASK_*_SUMMARY.md`
- Check [tasks.md](.kiro/specs/realtime-audio-transcription/tasks.md) for upcoming work
- Read [design.md](.kiro/specs/realtime-audio-transcription/design.md) for architecture details

### Deploy
- Read [DEPLOYMENT.md](DEPLOYMENT.md) for deployment procedures
- Set up AWS credentials
- Deploy to dev environment

## Getting Help

- **Documentation**: Check `README.md` and `docs/` folder
- **Specifications**: See `.kiro/specs/realtime-audio-transcription/`
- **Issues**: Check test output and logs
- **Team**: Ask Developer 3 (Translation & Integration Engineer)

## Success Checklist

After completing this quick start, you should be able to:

- ✅ Install dependencies
- ✅ Run all tests successfully (94 tests passing)
- ✅ Import and use shared modules
- ✅ Format and lint code
- ✅ Understand project structure
- ✅ Make changes and run tests

**Congratulations!** You're ready to contribute to the audio-transcription component.
