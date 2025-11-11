"""
CDK stack for Audio Transcription component with partial results processing.

This stack defines the infrastructure for real-time audio transcription including:
- Lambda function for audio processing with partial results
- CloudWatch alarms for monitoring
- IAM roles and permissions
"""

from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_ssm as ssm,
)
from constructs import Construct
import json


class AudioTranscriptionStack(Stack):
    """
    CDK stack for Audio Transcription component.
    
    Includes:
    - Audio Processor Lambda function with partial results processing
    - CloudWatch alarms for latency, rate limiting, and orphaned results
    - IAM roles with least privilege permissions
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create SNS topic for alarms
        alarm_topic = sns.Topic(
            self,
            'AudioTranscriptionAlarmTopic',
            display_name='Audio Transcription Alarms',
            topic_name='audio-transcription-alarms'
        )

        # Create feature flag parameter for gradual rollout
        feature_flag_parameter = self._create_feature_flag_parameter()

        # Create Lambda execution role
        lambda_role = self._create_lambda_role(feature_flag_parameter)

        # Create Audio Processor Lambda function
        audio_processor = self._create_audio_processor_lambda(lambda_role)

        # Create CloudWatch alarms
        self._create_cloudwatch_alarms(audio_processor, alarm_topic)

    def _create_feature_flag_parameter(self) -> ssm.StringParameter:
        """
        Create SSM parameter for feature flag configuration.
        
        This parameter enables dynamic configuration of partial results processing
        without redeployment. Supports gradual rollout with percentage-based
        canary deployment (10% → 50% → 100%).
        
        Returns:
            SSM parameter for feature flag configuration
        """
        # Default configuration: 100% rollout, partial results enabled
        default_config = {
            'enabled': True,
            'rollout_percentage': 100,
            'min_stability_threshold': 0.85,
            'max_buffer_timeout': 5.0
        }
        
        parameter = ssm.StringParameter(
            self,
            'PartialResultsFeatureFlagParameter',
            parameter_name='/audio-transcription/partial-results/config',
            string_value=json.dumps(default_config),
            description='Feature flag configuration for partial results processing with gradual rollout support',
            tier=ssm.ParameterTier.STANDARD
        )
        
        return parameter

    def _create_lambda_role(self, feature_flag_parameter: ssm.StringParameter) -> iam.Role:
        """
        Create IAM role for Lambda function with required permissions.
        
        Returns:
            IAM role with permissions for Transcribe, DynamoDB, CloudWatch
        """
        role = iam.Role(
            self,
            'AudioProcessorLambdaRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            description='Execution role for Audio Processor Lambda'
        )

        # Basic Lambda execution permissions
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                'service-role/AWSLambdaBasicExecutionRole'
            )
        )

        # AWS Transcribe permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'transcribe:StartStreamTranscription',
                    'transcribe:StartStreamTranscriptionWebSocket'
                ],
                resources=['*']
            )
        )

        # CloudWatch metrics permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'cloudwatch:PutMetricData'
                ],
                resources=['*'],
                conditions={
                    'StringEquals': {
                        'cloudwatch:namespace': 'AudioTranscription/PartialResults'
                    }
                }
            )
        )

        # DynamoDB permissions (for session configuration)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'dynamodb:GetItem',
                    'dynamodb:Query'
                ],
                resources=[
                    f'arn:aws:dynamodb:{self.region}:{self.account}:table/Sessions',
                    f'arn:aws:dynamodb:{self.region}:{self.account}:table/Sessions/index/*'
                ]
            )
        )

        # SSM Parameter Store permissions (for feature flags)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'ssm:GetParameter',
                    'ssm:GetParameters'
                ],
                resources=[
                    feature_flag_parameter.parameter_arn
                ]
            )
        )

        return role

    def _create_audio_processor_lambda(self, role: iam.Role) -> lambda_.Function:
        """
        Create Audio Processor Lambda function with partial results configuration.
        
        Args:
            role: IAM role for Lambda execution
            
        Returns:
            Lambda function configured for partial results processing
        """
        function = lambda_.Function(
            self,
            'AudioProcessorFunction',
            function_name='audio-processor',
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler='handler.lambda_handler',
            code=lambda_.Code.from_asset('lambda/audio_processor'),
            role=role,
            memory_size=512,  # Increased from 256 MB for buffers and cache
            timeout=Duration.seconds(60),  # Increased from 30s for orphan cleanup
            environment={
                # Feature flag configuration
                'FEATURE_FLAG_PARAMETER_NAME': '/audio-transcription/partial-results/config',
                'FEATURE_FLAG_CACHE_TTL': '60',  # Cache for 60 seconds
                
                # Partial results configuration (fallback if SSM unavailable)
                'PARTIAL_RESULTS_ENABLED': 'true',
                'ROLLOUT_PERCENTAGE': '100',
                'MIN_STABILITY_THRESHOLD': '0.85',
                'MAX_BUFFER_TIMEOUT': '5.0',
                'PAUSE_THRESHOLD': '2.0',
                'ORPHAN_TIMEOUT': '15.0',
                'MAX_RATE_PER_SECOND': '5',
                'DEDUP_CACHE_TTL': '10',
                
                # AWS service configuration
                'AWS_REGION': self.region,
                'SESSIONS_TABLE_NAME': 'Sessions',
                
                # Logging configuration
                'LOG_LEVEL': 'INFO',  # Set to DEBUG for verbose logging
                'STRUCTURED_LOGGING': 'true'
            },
            description='Audio processor with partial results processing for real-time transcription'
        )

        return function

    def _create_cloudwatch_alarms(
        self,
        lambda_function: lambda_.Function,
        alarm_topic: sns.Topic
    ) -> None:
        """
        Create CloudWatch alarms for monitoring partial results processing.
        
        Args:
            lambda_function: Lambda function to monitor
            alarm_topic: SNS topic for alarm notifications
        """
        # Alarm 1: End-to-end latency p95 > 5 seconds (CRITICAL)
        latency_alarm = cloudwatch.Alarm(
            self,
            'PartialResultLatencyAlarm',
            alarm_name='audio-transcription-latency-high',
            alarm_description='End-to-end latency p95 exceeds 5 seconds',
            metric=cloudwatch.Metric(
                namespace='AudioTranscription/PartialResults',
                metric_name='PartialResultProcessingLatency',
                statistic='p95',
                period=Duration.minutes(5)
            ),
            threshold=5000,  # 5 seconds in milliseconds
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        latency_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

        # Alarm 2: Partial results dropped > 100/minute (WARNING)
        dropped_alarm = cloudwatch.Alarm(
            self,
            'PartialResultsDroppedAlarm',
            alarm_name='audio-transcription-rate-limit-high',
            alarm_description='Partial results dropped exceeds 100 per minute',
            metric=cloudwatch.Metric(
                namespace='AudioTranscription/PartialResults',
                metric_name='PartialResultsDropped',
                statistic='Sum',
                period=Duration.minutes(1)
            ),
            threshold=100,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        dropped_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

        # Alarm 3: Orphaned results > 10/session (WARNING)
        orphaned_alarm = cloudwatch.Alarm(
            self,
            'OrphanedResultsAlarm',
            alarm_name='audio-transcription-orphaned-results-high',
            alarm_description='Orphaned results exceed 10 per session',
            metric=cloudwatch.Metric(
                namespace='AudioTranscription/PartialResults',
                metric_name='OrphanedResultsFlushed',
                statistic='Sum',
                period=Duration.minutes(5)
            ),
            threshold=10,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        orphaned_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

        # Alarm 4: Transcribe fallback triggered (CRITICAL)
        fallback_alarm = cloudwatch.Alarm(
            self,
            'TranscribeFallbackAlarm',
            alarm_name='audio-transcription-transcribe-fallback',
            alarm_description='Transcribe service fallback to final-only mode triggered',
            metric=cloudwatch.Metric(
                namespace='AudioTranscription/PartialResults',
                metric_name='TranscribeFallbackTriggered',
                statistic='Sum',
                period=Duration.minutes(5)
            ),
            threshold=1,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        fallback_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

        # Lambda function errors alarm
        error_alarm = cloudwatch.Alarm(
            self,
            'LambdaErrorAlarm',
            alarm_name='audio-transcription-lambda-errors',
            alarm_description='Lambda function errors detected',
            metric=lambda_function.metric_errors(
                period=Duration.minutes(5),
                statistic='Sum'
            ),
            threshold=5,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        error_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

        # Lambda function throttles alarm
        throttle_alarm = cloudwatch.Alarm(
            self,
            'LambdaThrottleAlarm',
            alarm_name='audio-transcription-lambda-throttles',
            alarm_description='Lambda function throttles detected',
            metric=lambda_function.metric_throttles(
                period=Duration.minutes(5),
                statistic='Sum'
            ),
            threshold=10,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        throttle_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))
