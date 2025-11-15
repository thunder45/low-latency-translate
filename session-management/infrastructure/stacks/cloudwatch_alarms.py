"""
CloudWatch Alarms for WebSocket Audio Integration.

This module defines CloudWatch alarms for monitoring audio processing,
control messages, session status, and error conditions.
"""

from aws_cdk import (
    Duration,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
)
from constructs import Construct


class CloudWatchAlarms(Construct):
    """
    CloudWatch alarms for WebSocket audio integration monitoring.
    
    Creates alarms for:
    - Audio processing latency
    - Transcribe errors
    - Lambda errors
    - Control message latency
    - Rate limit violations
    """
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        alarm_topic: sns.Topic
    ):
        """
        Initialize CloudWatch alarms.
        
        Args:
            scope: CDK scope
            construct_id: Construct identifier
            env_name: Environment name (dev, staging, prod)
            alarm_topic: SNS topic for alarm notifications
        """
        super().__init__(scope, construct_id)
        
        self.env_name = env_name
        self.alarm_action = cw_actions.SnsAction(alarm_topic)
        
        # Create alarms
        self._create_audio_processing_alarms()
        self._create_transcribe_alarms()
        self._create_lambda_alarms()
        self._create_control_message_alarms()
        self._create_rate_limit_alarms()
    
    def _create_audio_processing_alarms(self) -> None:
        """Create alarms for audio processing metrics."""
        
        # Critical: Audio latency p95 >100ms for 5 minutes
        cloudwatch.Alarm(
            self,
            'AudioLatencyP95Critical',
            alarm_name=f'{self.env_name}-audio-latency-p95-critical',
            alarm_description='Audio processing latency p95 exceeds 100ms',
            metric=cloudwatch.Metric(
                namespace='AudioTranscription/WebSocket',
                metric_name='AudioProcessingLatency',
                statistic='p95',
                period=Duration.minutes(1)
            ),
            threshold=100,
            evaluation_periods=5,
            datapoints_to_alarm=5,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
        
        # Warning: Audio latency p95 >75ms for 10 minutes
        cloudwatch.Alarm(
            self,
            'AudioLatencyP95Warning',
            alarm_name=f'{self.env_name}-audio-latency-p95-warning',
            alarm_description='Audio processing latency p95 exceeds 75ms',
            metric=cloudwatch.Metric(
                namespace='AudioTranscription/WebSocket',
                metric_name='AudioProcessingLatency',
                statistic='p95',
                period=Duration.minutes(1)
            ),
            threshold=75,
            evaluation_periods=10,
            datapoints_to_alarm=8,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
        
        # Audio buffer overflows
        cloudwatch.Alarm(
            self,
            'AudioBufferOverflows',
            alarm_name=f'{self.env_name}-audio-buffer-overflows',
            alarm_description='Audio buffer overflows detected',
            metric=cloudwatch.Metric(
                namespace='AudioTranscription/WebSocket',
                metric_name='AudioBufferOverflows',
                statistic='Sum',
                period=Duration.minutes(5)
            ),
            threshold=10,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
    
    def _create_transcribe_alarms(self) -> None:
        """Create alarms for Transcribe service metrics."""
        
        # Critical: Transcribe error rate >5% for 5 minutes
        transcribe_errors = cloudwatch.Metric(
            namespace='AudioTranscription/WebSocket',
            metric_name='TranscribeStreamErrors',
            statistic='Sum',
            period=Duration.minutes(1)
        )
        
        audio_chunks = cloudwatch.Metric(
            namespace='AudioTranscription/WebSocket',
            metric_name='AudioChunksReceived',
            statistic='Sum',
            period=Duration.minutes(1)
        )
        
        error_rate = cloudwatch.MathExpression(
            expression='(errors / chunks) * 100',
            using_metrics={
                'errors': transcribe_errors,
                'chunks': audio_chunks
            },
            period=Duration.minutes(1)
        )
        
        cloudwatch.Alarm(
            self,
            'TranscribeErrorRateCritical',
            alarm_name=f'{self.env_name}-transcribe-error-rate-critical',
            alarm_description='Transcribe error rate exceeds 5%',
            metric=error_rate,
            threshold=5,
            evaluation_periods=5,
            datapoints_to_alarm=5,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
        
        # Transcribe stream initialization latency
        cloudwatch.Alarm(
            self,
            'TranscribeInitLatency',
            alarm_name=f'{self.env_name}-transcribe-init-latency',
            alarm_description='Transcribe stream initialization latency high',
            metric=cloudwatch.Metric(
                namespace='AudioTranscription/WebSocket',
                metric_name='TranscribeStreamInitLatency',
                statistic='p95',
                period=Duration.minutes(5)
            ),
            threshold=2000,  # 2 seconds
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
    
    def _create_lambda_alarms(self) -> None:
        """Create alarms for Lambda function errors."""
        
        # Critical: Lambda error rate >1% for 5 minutes
        lambda_errors = cloudwatch.Metric(
            namespace='SessionManagement/WebSocket',
            metric_name='LambdaErrors',
            statistic='Sum',
            period=Duration.minutes(1)
        )
        
        control_messages = cloudwatch.Metric(
            namespace='SessionManagement/WebSocket',
            metric_name='ControlMessagesReceived',
            statistic='Sum',
            period=Duration.minutes(1)
        )
        
        error_rate = cloudwatch.MathExpression(
            expression='(errors / (messages + 1)) * 100',
            using_metrics={
                'errors': lambda_errors,
                'messages': control_messages
            },
            period=Duration.minutes(1)
        )
        
        cloudwatch.Alarm(
            self,
            'LambdaErrorRateCritical',
            alarm_name=f'{self.env_name}-lambda-error-rate-critical',
            alarm_description='Lambda error rate exceeds 1%',
            metric=error_rate,
            threshold=1,
            evaluation_periods=5,
            datapoints_to_alarm=5,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
        
        # DynamoDB errors
        cloudwatch.Alarm(
            self,
            'DynamoDBErrors',
            alarm_name=f'{self.env_name}-dynamodb-errors',
            alarm_description='DynamoDB errors detected',
            metric=cloudwatch.Metric(
                namespace='SessionManagement/WebSocket',
                metric_name='DynamoDBErrors',
                statistic='Sum',
                period=Duration.minutes(5)
            ),
            threshold=10,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
    
    def _create_control_message_alarms(self) -> None:
        """Create alarms for control message metrics."""
        
        # Warning: Control latency p95 >150ms for 10 minutes
        cloudwatch.Alarm(
            self,
            'ControlLatencyP95Warning',
            alarm_name=f'{self.env_name}-control-latency-p95-warning',
            alarm_description='Control message latency p95 exceeds 150ms',
            metric=cloudwatch.Metric(
                namespace='SessionManagement/WebSocket',
                metric_name='ControlMessageLatency',
                statistic='p95',
                period=Duration.minutes(1)
            ),
            threshold=150,
            evaluation_periods=10,
            datapoints_to_alarm=8,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
        
        # Listener notification failures
        cloudwatch.Alarm(
            self,
            'ListenerNotificationFailures',
            alarm_name=f'{self.env_name}-listener-notification-failures',
            alarm_description='High rate of listener notification failures',
            metric=cloudwatch.Metric(
                namespace='SessionManagement/WebSocket',
                metric_name='ListenerNotificationFailures',
                statistic='Sum',
                period=Duration.minutes(5)
            ),
            threshold=50,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
    
    def _create_rate_limit_alarms(self) -> None:
        """Create alarms for rate limiting metrics."""
        
        # Warning: Rate limit violations >100/min
        cloudwatch.Alarm(
            self,
            'RateLimitViolations',
            alarm_name=f'{self.env_name}-rate-limit-violations',
            alarm_description='High rate of rate limit violations',
            metric=cloudwatch.Metric(
                namespace='AudioTranscription/WebSocket',
                metric_name='RateLimitViolations',
                statistic='Sum',
                period=Duration.minutes(1)
            ),
            threshold=100,
            evaluation_periods=3,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
        
        # Connections closed for rate limiting
        cloudwatch.Alarm(
            self,
            'ConnectionsClosedForRateLimit',
            alarm_name=f'{self.env_name}-connections-closed-rate-limit',
            alarm_description='Connections being closed due to rate limiting',
            metric=cloudwatch.Metric(
                namespace='AudioTranscription/WebSocket',
                metric_name='ConnectionsClosedForRateLimit',
                statistic='Sum',
                period=Duration.minutes(5)
            ),
            threshold=10,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        ).add_alarm_action(self.alarm_action)
