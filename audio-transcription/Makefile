.PHONY: help install install-dev test test-unit test-integration coverage lint format type-check security-check deploy-dev deploy-staging deploy-prod destroy-dev destroy-staging destroy-prod synth bootstrap validate clean

# Default target - show help
help:
	@echo 'Audio Transcription Infrastructure - Makefile'
	@echo ''
	@echo 'Available targets:'
	@echo '  Setup:'
	@echo '    install          - Install all dependencies (runtime + dev)'
	@echo '    install-dev      - Install dev dependencies only'
	@echo ''
	@echo '  Testing:'
	@echo '    test             - Run all tests'
	@echo '    test-unit        - Run unit tests only'
	@echo '    test-integration - Run integration tests only'
	@echo '    coverage         - Generate coverage report'
	@echo ''
	@echo '  Code Quality:'
	@echo '    lint             - Run all linters'
	@echo '    format           - Format code with black'
	@echo '    type-check       - Run mypy type checking'
	@echo '    security-check   - Run bandit security scan'
	@echo ''
	@echo '  Deployment:'
	@echo '    deploy-dev       - Deploy to dev environment'
	@echo '    deploy-staging   - Deploy to staging'
	@echo '    deploy-prod      - Deploy to production'
	@echo '    destroy-dev      - Destroy dev stack'
	@echo '    destroy-staging  - Destroy staging stack'
	@echo '    destroy-prod     - Destroy prod stack (with confirmation)'
	@echo '    synth            - Synthesize CloudFormation template'
	@echo '    bootstrap        - Bootstrap CDK (first time only)'
	@echo ''
	@echo '  Validation:'
	@echo '    validate         - Validate project structure'
	@echo ''
	@echo '  Utilities:'
	@echo '    clean            - Clean build artifacts'

# Install all dependencies
install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	cd infrastructure && pip install -r requirements.txt

# Install dev dependencies only
install-dev:
	pip install -r requirements-dev.txt

# Run all tests
test:
	pytest tests/ -v --cov=shared --cov=lambda --cov-report=term-missing

# Run unit tests only
test-unit:
	pytest tests/unit/ -v

# Run integration tests only
test-integration:
	pytest tests/integration/ -v

# Generate coverage report
coverage:
	pytest tests/ --cov=shared --cov=lambda --cov-report=html --cov-report=term-missing
	@echo 'Coverage report generated in htmlcov/index.html'

# Run all linters
lint:
	@echo 'Running flake8...'
	flake8 shared/ lambda/ || true
	@echo 'Running pylint...'
	pylint shared/ lambda/ || true
	@echo 'Running mypy...'
	mypy shared/ lambda/ || true

# Format code
format:
	@echo 'Running black...'
	black shared/ lambda/ tests/
	@echo 'Code formatting complete!'

# Type checking
type-check:
	mypy shared/ lambda/

# Security scanning
security-check:
	bandit -r shared/ lambda/ -ll

# Deploy to dev environment
deploy-dev:
	cd infrastructure && cdk deploy --context env=dev --require-approval never

# Deploy to staging environment
deploy-staging:
	cd infrastructure && cdk deploy --context env=staging --require-approval never

# Deploy to production environment
deploy-prod:
	cd infrastructure && cdk deploy --context env=prod

# Destroy dev environment
destroy-dev:
	cd infrastructure && cdk destroy --context env=dev --force

# Destroy staging environment
destroy-staging:
	cd infrastructure && cdk destroy --context env=staging --force

# Destroy production environment (requires manual confirmation)
destroy-prod:
	@echo "WARNING: You are about to destroy the PRODUCTION environment!"
	@echo "This action cannot be undone. Type 'yes' to continue:"
	@read -r confirm && [ "$$confirm" = "yes" ] && cd infrastructure && cdk destroy --context env=prod --force || echo "Aborted."

# Synthesize CloudFormation template
synth:
	cd infrastructure && cdk synth --context env=dev

# Bootstrap CDK (first time only)
bootstrap:
	cd infrastructure && cdk bootstrap

# Validate project structure
validate:
	python validate_structure.py

# Clean build artifacts
clean:
	@echo 'Cleaning build artifacts...'
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	rm -rf build/
	rm -rf dist/
	rm -rf infrastructure/cdk.out
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	@echo 'Clean complete!'
