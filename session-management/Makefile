.PHONY: install test lint format deploy clean

# Install dependencies
install:
	pip install -r requirements.txt
	cd infrastructure && pip install -r requirements.txt

# Run tests
test:
	pytest tests/ -v --cov=shared --cov=lambda

# Lint code
lint:
	flake8 lambda/ shared/ tests/
	mypy lambda/ shared/

# Format code
format:
	black lambda/ shared/ tests/ infrastructure/

# Deploy infrastructure
deploy-dev:
	cd infrastructure && cdk deploy --context env=dev

deploy-staging:
	cd infrastructure && cdk deploy --context env=staging

deploy-prod:
	cd infrastructure && cdk deploy --context env=prod

# Synthesize CloudFormation template
synth:
	cd infrastructure && cdk synth --context env=dev

# Bootstrap CDK (first time only)
bootstrap:
	cd infrastructure && cdk bootstrap

# Clean build artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name *.egg-info -exec rm -rf {} +
	rm -rf infrastructure/cdk.out
	rm -rf .coverage
	rm -rf htmlcov/
