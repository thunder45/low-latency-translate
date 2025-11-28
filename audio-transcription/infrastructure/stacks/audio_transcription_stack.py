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
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_ssm as ssm,
    aws_s3 as s3,
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

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str = 'dev',
        config: dict = None,
        session_management_stack=None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.env_name = env_name
        self.config = config or {}
        self.session_management_stack = session_management_stack

        # Create SNS topic for alarms
        alarm_topic = sns.Topic(
            self,
            'AudioTranscriptionAlarmTopic',
            display_name='Audio Transcription Alarms',
            topic_name='audio-transcription-alarms'
        )

        # Create S3 bucket for translated audio (Phase 3)
        self.translated_audio_bucket = self._create_translated_audio_bucket()

        # Create feature flag parameter for gradual rollout
        feature_flag_parameter = self._create_feature_flag_parameter()

        # Create Lambda execution role
        lambda_role = self._create_lambda_role(feature_flag_parameter)

        # Create Audio Processor Lambda function
        self.audio_processor_function = self._create_audio_processor_lambda(lambda_role)
        
        # Grant S3 permissions to audio processor (Phase 3)
        self.translated_audio_bucket.grant_read_write(self.audio_processor_function)

        # Phase 4: Connect audio_processor to Kinesis Data Stream
        if session_management_stack and hasattr(session_management_stack, 'audio_stream'):
            self._configure_kinesis_event_source(session_management_stack.audio_stream)

        # Create CloudWatch alarms
        self._create_cloudwatch_alarms(self.audio_processor_function, alarm_topic)

        # Create CloudWatch dashboard
        self._create_cloudwatch_dashboard(self.audio_processor_function)

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
                    'transcribe:StartStreamTranscriptionWebSocket',
                    'transcribe:StartTranscriptionJob',
                    'transcribe:GetTranscriptionJob',
                    'transcribe:DeleteTranscriptionJob'
                ],
                resources=['*']
            )
        )
        
        # AWS Translate permissions (Phase 3)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'translate:TranslateText'
                ],
                resources=['*']
            )
        )
        
        # AWS Polly TTS permissions (Phase 3)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'polly:SynthesizeSpeech'
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
                        'cloudwatch:namespace': [
                            'AudioTranscription/PartialResults',
                            'AudioQuality'
                        ]
                    }
                }
            )
        )

        # EventBridge permissions for audio quality events
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'events:PutEvents'
                ],
                resources=[
                    f'arn:aws:events:{self.region}:{self.account}:event-bus/default'
                ]
            )
        )

        # DynamoDB permissions (for session and connections)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'dynamodb:GetItem',
                    'dynamodb:Query'
                ],
                resources=[
                    f'arn:aws:dynamodb:{self.region}:{self.account}:table/Sessions*',
                    f'arn:aws:dynamodb:{self.region}:{self.account}:table/Connections*',
                ]
            )
        )
        
        # API Gateway ManageConnections permissions (Phase 3)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'execute-api:ManageConnections',
                    'execute-api:Invoke'
                ],
                resources=[
                    f'arn:aws:execute-api:{self.region}:{self.account}:*/*/*/*'
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

        # Lambda invoke permissions (for Translation Pipeline)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'lambda:InvokeFunction',
                    'lambda:InvokeAsync'
                ],
                resources=[
                    f'arn:aws:lambda:{self.region}:{self.account}:function:TranslationProcessor'
                ]
            )
        )
        
        # S3 permissions for audio chunks bucket (Phase 3 - for Transcribe temp storage)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    's3:PutObject',
                    's3:GetObject',
                    's3:DeleteObject'
                ],
                resources=[
                    f'arn:aws:s3:::low-latency-audio-{self.env_name}/*'
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
        # Get the path to lambda directory (relative to infrastructure/stacks directory)
        import os
        lambda_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'lambda',
            'audio_processor'
        )
        
        function = lambda_.Function(
            self,
            'AudioProcessorFunction',
            function_name='audio-processor',
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler='handler.lambda_handler',
            code=lambda_.Code.from_asset(lambda_path),
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
                
                # Audio quality validation configuration
                'AUDIO_QUALITY_ENABLED': 'true',
                'SNR_THRESHOLD_DB': '20.0',
                'SNR_UPDATE_INTERVAL_MS': '500',
                'SNR_WINDOW_SIZE_S': '5.0',
                'CLIPPING_THRESHOLD_PERCENT': '1.0',
                'CLIPPING_AMPLITUDE_PERCENT': '98.0',
                'CLIPPING_WINDOW_MS': '100',
                'ECHO_THRESHOLD_DB': '-15.0',
                'ECHO_MIN_DELAY_MS': '10',
                'ECHO_MAX_DELAY_MS': '500',
                'ECHO_UPDATE_INTERVAL_S': '1.0',
                'SILENCE_THRESHOLD_DB': '-50.0',
                'SILENCE_DURATION_THRESHOLD_S': '5.0',
                'ENABLE_HIGH_PASS': 'false',
                'ENABLE_NOISE_GATE': 'false',
                'CLOUDWATCH_METRICS_ENABLED': 'true',
                'EVENTBRIDGE_EVENTS_ENABLED': 'true',
                
                # AWS service configuration
                # Note: AWS_REGION is automatically set by Lambda runtime
                'SESSIONS_TABLE_NAME': 'Sessions',
                'CONNECTIONS_TABLE': f'Connections-{self.env_name}',
                'TRANSLATION_PIPELINE_FUNCTION_NAME': 'TranslationProcessor',
                'S3_BUCKET_NAME': f'translation-audio-{self.env_name}',
                'AUDIO_BUCKET_NAME': f'low-latency-audio-{self.env_name}',  # For Transcribe temp storage
                'PRESIGNED_URL_EXPIRATION': '600',  # 10 minutes
                'STAGE': self.env_name,
                # API_GATEWAY_ENDPOINT will be set by session-management stack after deployment
                'API_GATEWAY_ENDPOINT': 'wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod',
                
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

        # Audio Quality Alarms

        # Alarm 5: Low SNR (threshold: 15 dB, 2 evaluation periods)
        snr_alarm = cloudwatch.Alarm(
            self,
            'AudioQualitySNRAlarm',
            alarm_name='audio-quality-snr-low',
            alarm_description='Audio SNR below 15 dB threshold',
            metric=cloudwatch.Metric(
                namespace='AudioQuality',
                metric_name='SNR',
                statistic='Average',
                period=Duration.minutes(5)
            ),
            threshold=15.0,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        snr_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

        # Alarm 6: High clipping (threshold: 5%, 3 evaluation periods)
        clipping_alarm = cloudwatch.Alarm(
            self,
            'AudioQualityClippingAlarm',
            alarm_name='audio-quality-clipping-high',
            alarm_description='Audio clipping exceeds 5% threshold',
            metric=cloudwatch.Metric(
                namespace='AudioQuality',
                metric_name='ClippingPercentage',
                statistic='Average',
                period=Duration.minutes(5)
            ),
            threshold=5.0,
            evaluation_periods=3,
            datapoints_to_alarm=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        clipping_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

    def _create_cloudwatch_dashboard(self, lambda_function: lambda_.Function) -> None:
        """
        Create CloudWatch dashboard for audio quality monitoring.
        
        Dashboard includes widgets for:
        - SNR (Signal-to-Noise Ratio)
        - Clipping percentage
        - Echo level
        - Silence duration
        - Processing latency histogram
        
        Args:
            lambda_function: Lambda function to monitor
        """
        dashboard = cloudwatch.Dashboard(
            self,
            'AudioQualityDashboard',
            dashboard_name='audio-quality-monitoring'
        )

        # SNR widget
        snr_widget = cloudwatch.GraphWidget(
            title='Signal-to-Noise Ratio (SNR)',
            left=[
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='SNR',
                    statistic='Average',
                    period=Duration.minutes(1),
                    label='Average SNR'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='SNR',
                    statistic='Minimum',
                    period=Duration.minutes(1),
                    label='Minimum SNR'
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(
                label='SNR (dB)',
                min=0,
                max=50
            ),
            width=12,
            height=6
        )

        # Clipping widget
        clipping_widget = cloudwatch.GraphWidget(
            title='Audio Clipping',
            left=[
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='ClippingPercentage',
                    statistic='Average',
                    period=Duration.minutes(1),
                    label='Average Clipping %'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='ClippingPercentage',
                    statistic='Maximum',
                    period=Duration.minutes(1),
                    label='Maximum Clipping %'
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(
                label='Clipping (%)',
                min=0,
                max=10
            ),
            width=12,
            height=6
        )

        # Echo level widget
        echo_widget = cloudwatch.GraphWidget(
            title='Echo Detection',
            left=[
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='EchoLevel',
                    statistic='Average',
                    period=Duration.minutes(1),
                    label='Average Echo Level'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='EchoLevel',
                    statistic='Maximum',
                    period=Duration.minutes(1),
                    label='Maximum Echo Level'
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(
                label='Echo Level (dB)',
                min=-100,
                max=0
            ),
            width=12,
            height=6
        )

        # Silence duration widget
        silence_widget = cloudwatch.GraphWidget(
            title='Silence Detection',
            left=[
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='SilenceDuration',
                    statistic='Average',
                    period=Duration.minutes(1),
                    label='Average Silence Duration'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='SilenceDuration',
                    statistic='Maximum',
                    period=Duration.minutes(1),
                    label='Maximum Silence Duration'
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(
                label='Duration (seconds)',
                min=0
            ),
            width=12,
            height=6
        )

        # Processing latency histogram
        latency_widget = cloudwatch.GraphWidget(
            title='Audio Quality Processing Latency',
            left=[
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='ProcessingLatency',
                    statistic='Average',
                    period=Duration.minutes(1),
                    label='Average Latency'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='ProcessingLatency',
                    statistic='p50',
                    period=Duration.minutes(1),
                    label='p50 Latency'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='ProcessingLatency',
                    statistic='p95',
                    period=Duration.minutes(1),
                    label='p95 Latency'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='ProcessingLatency',
                    statistic='p99',
                    period=Duration.minutes(1),
                    label='p99 Latency'
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(
                label='Latency (ms)',
                min=0
            ),
            width=12,
            height=6
        )

        # Quality events widget
        events_widget = cloudwatch.GraphWidget(
            title='Quality Events',
            left=[
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='QualityWarnings',
                    statistic='Sum',
                    period=Duration.minutes(5),
                    label='Total Warnings'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='SNRLowEvents',
                    statistic='Sum',
                    period=Duration.minutes(5),
                    label='SNR Low Events'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='ClippingEvents',
                    statistic='Sum',
                    period=Duration.minutes(5),
                    label='Clipping Events'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='EchoEvents',
                    statistic='Sum',
                    period=Duration.minutes(5),
                    label='Echo Events'
                ),
                cloudwatch.Metric(
                    namespace='AudioQuality',
                    metric_name='SilenceEvents',
                    statistic='Sum',
                    period=Duration.minutes(5),
                    label='Silence Events'
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(
                label='Event Count',
                min=0
            ),
            width=12,
            height=6
        )

        # Lambda function metrics
        lambda_widget = cloudwatch.GraphWidget(
            title='Lambda Function Metrics',
            left=[
                lambda_function.metric_invocations(
                    statistic='Sum',
                    period=Duration.minutes(1),
                    label='Invocations'
                ),
                lambda_function.metric_errors(
                    statistic='Sum',
                    period=Duration.minutes(1),
                    label='Errors'
                ),
                lambda_function.metric_throttles(
                    statistic='Sum',
                    period=Duration.minutes(1),
                    label='Throttles'
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(
                label='Count',
                min=0
            ),
            width=12,
            height=6
        )

        # Add widgets to dashboard
        dashboard.add_widgets(snr_widget, clipping_widget)
        dashboard.add_widgets(echo_widget, silence_widget)
        dashboard.add_widgets(latency_widget, events_widget)
        dashboard.add_widgets(lambda_widget)

    def _configure_kinesis_event_source(self, kinesis_stream) -> None:
        """
        Configure Kinesis Data Stream as event source for audio_processor (Phase 4).
        
        This replaces S3-based event triggering with native Kinesis batching:
        - BatchWindow: 3 seconds (wait for 3s of records)
        - BatchSize: 100 records max per invocation
        - ParallelizationFactor: 10 (process 10 shards in parallel)
        
        Benefits:
        - Native batching (no race conditions)
        - 92% fewer Lambda invocations
        - Predictable processing windows
        
        Args:
            kinesis_stream: Kinesis Data Stream from session_management_stack
        """
        from aws_cdk import aws_lambda_event_sources as event_sources
        
        # Add Kinesis stream as event source
        self.audio_processor_function.add_event_source(
            event_sources.KinesisEventSource(
                stream=kinesis_stream,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=100,  # Max records per invocation
                max_batching_window=Duration.seconds(3),  # Wait 3 seconds for batching
                parallelization_factor=10,  # Process 10 shards in parallel
                retry_attempts=2,  # Retry failed batches
                max_record_age=Duration.hours(24),  # Skip records older than 24 hours
                bisect_batch_on_error=True,  # Split batch on error for better error isolation
            )
        )
        
        # Grant Kinesis read permissions (automatically done by add_event_source, but explicit)
        kinesis_stream.grant_read(self.audio_processor_function)

    def _create_translated_audio_bucket(self) -> s3.Bucket:
        """
        Create S3 bucket for translated audio storage (Phase 3).
        
        Returns:
            S3 bucket for translated audio with lifecycle policy
        """
        bucket = s3.Bucket(
            self,
            'TranslatedAudioBucket',
            bucket_name=f'translation-audio-{self.env_name}',
            removal_policy=RemovalPolicy.DESTROY if self.env_name == 'dev' else RemovalPolicy.RETAIN,
            auto_delete_objects=True if self.env_name == 'dev' else False,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id='DeleteOldTranslatedAudio',
                    expiration=Duration.days(1),  # Auto-delete after 24 hours
                    enabled=True,
                )
            ],
            # CORS for listener access
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET],
                    allowed_origins=['*'],  # TODO: Restrict to your domains in production
                    allowed_headers=['*'],
                    max_age=3600,
                )
            ],
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=False,
        )
        return bucket
