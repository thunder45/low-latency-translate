.PHONY: help install install-dev test test-unit test-integration test-e2e test-resilience coverage lint format type-check security-check deploy-dev deploy-staging deploy-prod destroy-dev destroy-staging destroy-prod synth bootstrap validate validate-cdk logs-dev clean

# Default target - show help
help:
	@echo 'Session Management & WebSocket Infrastructure - Makefile'
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
	@echo '    test-e2e         - Run E2E tests (requires AWS)'
	@echo '    test-resilience  - Run resilience tests'
	@echo '    coverage         - Generate coverage report'
	@echo ''
	@echo '  Code Quality:'
	@echo '    lint             - Run all linters'
	@echo '    format           - Format code with black and isort'
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
	@echo '    validate-cdk     - Validate CDK code'
	@echo ''
	@echo '  Utilities:'
	@echo '    logs-dev         - Tail CloudWatch logs (dev)'
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
	pytest tests/unit/ -v -m unit

# Run integration tests only
test-integration:
	pytest tests/integration/ -v -m integration

# Run E2E tests (requires AWS infrastructure)
test-e2e:
	pytest tests/test_e2e_integration.py -v -m e2e

# Run resilience tests
test-resilience:
	pytest tests/test_resilience.py -v -m resilience

# Generate coverage report
coverage:
	pytest tests/ --cov=shared --cov=lambda --cov-report=html --cov-report=term-missing
	@echo 'Coverage report generated in htmlcov/index.html'

# Run all linters
lint:
	@echo 'Running flake8...'
	flake8 lambda/ shared/ tests/ infrastructure/
	@echo 'Running pylint...'
	pylint lambda/ shared/ --disable=C0111,R0903
	@echo 'Running mypy...'
	mypy lambda/ shared/

# Format code
format:
	@echo 'Running black...'
	black lambda/ shared/ tests/ infrastructure/
	@echo 'Running isort...'
	isort lambda/ shared/ tests/ infrastructure/

# Type checking
type-check:
	mypy lambda/ shared/ --strict

# Security scanning
security-check:
	bandit -r lambda/ shared/ -ll

# Deploy to dev environment
deploy-dev:
	cd infrastructure && cdk deploy --context env=dev --require-approval never

# Deploy to staging environment
deploy-staging:
	cd infrastructure && cdk deploy --context env=staging --require-approval broadening

# Deploy to production environment
deploy-prod:
	cd infrastructure && cdk deploy --context env=prod --require-approval broadening

# Destroy dev stack
destroy-dev:
	cd infrastructure && cdk destroy --context env=dev --force

# Destroy staging stack
destroy-staging:
	cd infrastructure && cdk destroy --context env=staging --force

# Destroy production stack (requires manual confirmation)
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

# Validate CDK code
validate-cdk:
	cd infrastructure && cdk synth --context env=dev --validation

# Tail CloudWatch logs for dev environment
logs-dev:
	@echo 'Tailing CloudWatch logs for dev environment...'
	@echo 'Use Ctrl+C to stop'
	aws logs tail /aws/lambda/session-management-dev --follow --format short

# Clean build artifacts
clean:
	@echo 'Cleaning build artifacts...'
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	rm -rf infrastructure/cdk.out
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf dist/
	rm -rf build/
	@echo 'Clean complete!'
