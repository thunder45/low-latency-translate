"""
Unit tests for Translation Pipeline Infrastructure.

Tests CDK stack synthesis and validates DynamoDB table configurations.
"""
import json
import pytest
from aws_cdk import App
from aws_cdk.assertions import Template, Match


def test_stack_synthesizes():
    """Test that the CDK stack can be synthesized without errors."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'infrastructure'))
    from stacks.translation_pipeline_stack import TranslationPipelineStack
    
    app = App()
    
    # Test configuration
    config = {
        "account": "123456789012",
        "region": "us-east-1",
        "alarmEmail": "test@example.com",
        "maxConcurrentBroadcasts": 100,
        "cacheTTLSeconds": 3600,
        "maxCacheEntries": 10000
    }
    
    # Create stack
    stack = TranslationPipelineStack(
        app,
        "TestTranslationPipelineStack",
        config=config,
        env_name="test"
    )
    
    # Synthesize stack
    template = Template.from_stack(stack)
    
    # Verify stack has resources
    assert template is not None


def test_sessions_table_created():
    """Test that Sessions table is created with correct configuration."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'infrastructure'))
    from stacks.translation_pipeline_stack import TranslationPipelineStack
    
    app = App()
    config = {
        "account": "123456789012",
        "region": "us-east-1"
    }
    
    stack = TranslationPipelineStack(
        app,
        "TestStack",
        config=config,
        env_name="test"
    )
    
    template = Template.from_stack(stack)
    
    # Verify Sessions table exists
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "Sessions-test",
            "BillingMode": "PAY_PER_REQUEST",
            "TimeToLiveSpecification": {
                "AttributeName": "expiresAt",
                "Enabled": True
            },
            "KeySchema": [
                {
                    "AttributeName": "sessionId",
                    "KeyType": "HASH"
                }
            ]
        }
    )


def test_connections_table_with_gsi():
    """Test that Connections table is created with GSI."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'infrastructure'))
    from stacks.translation_pipeline_stack import TranslationPipelineStack
    
    app = App()
    config = {
        "account": "123456789012",
        "region": "us-east-1"
    }
    
    stack = TranslationPipelineStack(
        app,
        "TestStack",
        config=config,
        env_name="test"
    )
    
    template = Template.from_stack(stack)
    
    # Verify Connections table with GSI
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "Connections-test",
            "BillingMode": "PAY_PER_REQUEST",
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "sessionId-targetLanguage-index",
                    "KeySchema": [
                        {
                            "AttributeName": "sessionId",
                            "KeyType": "HASH"
                        },
                        {
                            "AttributeName": "targetLanguage",
                            "KeyType": "RANGE"
                        }
                    ],
                    "Projection": {
                        "ProjectionType": "ALL"
                    }
                }
            ]
        }
    )


def test_cached_translations_table_with_ttl():
    """Test that CachedTranslations table is created with TTL."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'infrastructure'))
    from stacks.translation_pipeline_stack import TranslationPipelineStack
    
    app = App()
    config = {
        "account": "123456789012",
        "region": "us-east-1"
    }
    
    stack = TranslationPipelineStack(
        app,
        "TestStack",
        config=config,
        env_name="test"
    )
    
    template = Template.from_stack(stack)
    
    # Verify CachedTranslations table
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "CachedTranslations-test",
            "BillingMode": "PAY_PER_REQUEST",
            "TimeToLiveSpecification": {
                "AttributeName": "ttl",
                "Enabled": True
            },
            "KeySchema": [
                {
                    "AttributeName": "cacheKey",
                    "KeyType": "HASH"
                }
            ]
        }
    )


def test_cloudwatch_alarms_created():
    """Test that CloudWatch alarms are created."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'infrastructure'))
    from stacks.translation_pipeline_stack import TranslationPipelineStack
    
    app = App()
    config = {
        "account": "123456789012",
        "region": "us-east-1"
    }
    
    stack = TranslationPipelineStack(
        app,
        "TestStack",
        config=config,
        env_name="test"
    )
    
    template = Template.from_stack(stack)
    
    # Verify alarms exist
    template.resource_count_is("AWS::CloudWatch::Alarm", 4)
    
    # Verify cache hit rate alarm
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "translation-cache-hit-rate-low-test",
            "Threshold": 30,
            "ComparisonOperator": "LessThanThreshold"
        }
    )
    
    # Verify broadcast success rate alarm
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "broadcast-success-rate-low-test",
            "Threshold": 95,
            "ComparisonOperator": "LessThanThreshold"
        }
    )


def test_sns_topic_created():
    """Test that SNS topic for alarms is created."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'infrastructure'))
    from stacks.translation_pipeline_stack import TranslationPipelineStack
    
    app = App()
    config = {
        "account": "123456789012",
        "region": "us-east-1",
        "alarmEmail": "test@example.com"
    }
    
    stack = TranslationPipelineStack(
        app,
        "TestStack",
        config=config,
        env_name="test"
    )
    
    template = Template.from_stack(stack)
    
    # Verify SNS topic
    template.has_resource_properties(
        "AWS::SNS::Topic",
        {
            "TopicName": "translation-pipeline-alarms-test",
            "DisplayName": "Translation Pipeline CloudWatch Alarms"
        }
    )
    
    # Verify email subscription
    template.has_resource_properties(
        "AWS::SNS::Subscription",
        {
            "Protocol": "email",
            "Endpoint": "test@example.com"
        }
    )


def test_stack_outputs():
    """Test that stack outputs are created."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'infrastructure'))
    from stacks.translation_pipeline_stack import TranslationPipelineStack
    
    app = App()
    config = {
        "account": "123456789012",
        "region": "us-east-1"
    }
    
    stack = TranslationPipelineStack(
        app,
        "TestStack",
        config=config,
        env_name="test"
    )
    
    template = Template.from_stack(stack)
    
    # Verify outputs exist
    template.has_output("SessionsTableName", {})
    template.has_output("SessionsTableArn", {})
    template.has_output("ConnectionsTableName", {})
    template.has_output("ConnectionsTableArn", {})
    template.has_output("ConnectionsGSIName", {})
    template.has_output("CachedTranslationsTableName", {})
    template.has_output("CachedTranslationsTableArn", {})
    template.has_output("AlarmTopicArn", {})
