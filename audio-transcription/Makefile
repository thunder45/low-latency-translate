.PHONY: install test lint format clean deploy-dev deploy-staging deploy-prod

# Install dependencies
install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# Run tests
test:
	pytest

# Run linters
lint:
	pylint shared/ lambda/ || true
	flake8 shared/ lambda/ || true
	mypy shared/ lambda/ || true

# Format code
format:
	black shared/ lambda/ tests/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

# Deploy to dev environment
deploy-dev:
	cd infrastructure && cdk deploy --context env=dev --require-approval never

# Deploy to staging environment
deploy-staging:
	cd infrastructure && cdk deploy --context env=staging --require-approval never

# Deploy to production environment
deploy-prod:
	cd infrastructure && cdk deploy --context env=prod
