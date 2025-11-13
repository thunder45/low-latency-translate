# Task 14: Create Infrastructure Configuration

## Task Description
Created comprehensive infrastructure configuration for audio quality validation including Lambda environment variables, CloudWatch dashboard, and CloudWatch alarms.

## Task Instructions

### Task 14.1: Add Lambda environment variables
- Define environment variables in IaC (Terraform/CloudFormation)
- Set default values for quality thresholds
- Configure CloudWatch and EventBridge integration flags
- Requirements: 4.1, 4.2, 4.3, 4.4

### Task 14.2: Create CloudWatch dashboard
- Define dashboard JSON with widgets for SNR, clipping, echo, silence
- Add processing latency histogram
- Requirements: 5.1, 5.2

### Task 14.3: Create CloudWatch alarms
- Create alarm for low SNR (threshold: 15 dB, 2 evaluation periods)
- Create alarm for high clipping (threshold: 5%, 3 evaluation periods)
- Configure SNS topic for alarm notifications
- Requirements: 5.3

## Task Tests

No automated tests required for infrastructure configuration. Manual verification:

1. **CDK Synthesis**: Verify stack synthesizes without errors
   ```bash
   cd audio-transcription/infrastructure
   cdk synth
   ```

2. **Configuration Validation**: Verify environment variables are properly set
   - All audio quality thresholds defined
   - CloudWatch and EventBridge flags configured
   - Default values match requirements

3. **Dashboard Validation**: Verify dashboard includes all required widgets
   - SNR widget with average and minimum metrics
   - Clipping widget with average and maximum metrics
   - Echo level widget
   - Silence duration widget
   - Processing latency histogram (p50, p95, p99)
   - Quality events widget
   - Lambda function metrics

4. **Alarm Validation**: Verify alarms are properly configured
   - SNR alarm: threshold 15 dB, 2 evaluation periods
   - Clipping alarm: threshold 5%, 3 evaluation periods
   - Both alarms connected to SNS topic

## Task Solution

### 14.1: Lambda Environment Variables

**Modified Files**:
- `audio-transcription/infrastructure/stacks/audio_transcription_stack.py`
- `audio-transcription/infrastructure/config/dev.json.example`

**Implementation**:

1. **Added Audio Quality Environment Variables** to Lambda function:
   - `AUDIO_QUALITY_ENABLED`: Enable/disable audio quality validation
   - `SNR_THRESHOLD_DB`: SNR threshold (default: 20.0 dB)
   - `SNR_UPDATE_INTERVAL_MS`: SNR update interval (default: 500 ms)
   - `SNR_WINDOW_SIZE_S`: SNR rolling window size (default: 5.0 seconds)
   - `CLIPPING_THRESHOLD_PERCENT`: Clipping threshold (default: 1.0%)
   - `CLIPPING_AMPLITUDE_PERCENT`: Clipping amplitude threshold (default: 98.0%)
   - `CLIPPING_WINDOW_MS`: Clipping detection window (default: 100 ms)
   - `ECHO_THRESHOLD_DB`: Echo detection threshold (default: -15.0 dB)
   - `ECHO_MIN_DELAY_MS`: Minimum echo delay (default: 10 ms)
   - `ECHO_MAX_DELAY_MS`: Maximum echo delay (default: 500 ms)
   - `ECHO_UPDATE_INTERVAL_S`: Echo update interval (default: 1.0 second)
   - `SILENCE_THRESHOLD_DB`: Silence detection threshold (default: -50.0 dB)
   - `SILENCE_DURATION_THRESHOLD_S`: Silence duration threshold (default: 5.0 seconds)
   - `ENABLE_HIGH_PASS`: Enable high-pass filter (default: false)
   - `ENABLE_NOISE_GATE`: Enable noise gate (default: false)
   - `CLOUDWATCH_METRICS_ENABLED`: Enable CloudWatch metrics (default: true)
   - `EVENTBRIDGE_EVENTS_ENABLED`: Enable EventBridge events (default: true)

2. **Updated IAM Permissions**:
   - Added `AudioQuality` namespace to CloudWatch metrics permissions
   - Added EventBridge `PutEvents` permission for quality events

3. **Updated Configuration Example**:
   - Added `audio_quality` section to `dev.json.example`
   - Increased Lambda memory from 512 MB to 1024 MB for audio processing
   - Added alarm thresholds for SNR and clipping

### 14.2: CloudWatch Dashboard

**Modified Files**:
- `audio-transcription/infrastructure/stacks/audio_transcription_stack.py`

**Implementation**:

Created comprehensive CloudWatch dashboard named `audio-quality-monitoring` with the following widgets:

1. **SNR Widget** (12x6):
   - Average SNR metric
   - Minimum SNR metric
   - Y-axis: 0-50 dB

2. **Clipping Widget** (12x6):
   - Average clipping percentage
   - Maximum clipping percentage
   - Y-axis: 0-10%

3. **Echo Level Widget** (12x6):
   - Average echo level
   - Maximum echo level
   - Y-axis: -100 to 0 dB

4. **Silence Duration Widget** (12x6):
   - Average silence duration
   - Maximum silence duration
   - Y-axis: 0+ seconds

5. **Processing Latency Widget** (12x6):
   - Average latency
   - p50 latency
   - p95 latency
   - p99 latency
   - Y-axis: 0+ ms

6. **Quality Events Widget** (12x6):
   - Total quality warnings
   - SNR low events
   - Clipping events
   - Echo events
   - Silence events
   - 5-minute aggregation period

7. **Lambda Function Metrics Widget** (12x6):
   - Invocations
   - Errors
   - Throttles

All metrics use 1-minute periods (except events which use 5-minute periods) for real-time monitoring.

### 14.3: CloudWatch Alarms

**Modified Files**:
- `audio-transcription/infrastructure/stacks/audio_transcription_stack.py`

**Implementation**:

Created two audio quality alarms connected to the existing SNS alarm topic:

1. **SNR Low Alarm** (`audio-quality-snr-low`):
   - Metric: `AudioQuality/SNR` (Average)
   - Threshold: 15.0 dB
   - Evaluation periods: 2
   - Datapoints to alarm: 2
   - Period: 5 minutes
   - Comparison: Less than threshold
   - Description: "Audio SNR below 15 dB threshold"

2. **Clipping High Alarm** (`audio-quality-clipping-high`):
   - Metric: `AudioQuality/ClippingPercentage` (Average)
   - Threshold: 5.0%
   - Evaluation periods: 3
   - Datapoints to alarm: 3
   - Period: 5 minutes
   - Comparison: Greater than threshold
   - Description: "Audio clipping exceeds 5% threshold"

Both alarms:
- Use `NOT_BREACHING` for missing data treatment
- Send notifications to the existing `audio-transcription-alarms` SNS topic
- Follow AWS best practices for alarm configuration

## Key Design Decisions

1. **Environment Variable Defaults**: Set conservative defaults that work for most use cases while allowing runtime configuration without redeployment.

2. **Lambda Memory Increase**: Increased from 512 MB to 1024 MB to accommodate audio quality processing with librosa and numpy operations.

3. **Dashboard Layout**: Organized widgets in logical pairs (SNR/Clipping, Echo/Silence, Latency/Events) for easy visual correlation.

4. **Alarm Thresholds**: 
   - SNR: 15 dB (lower than operational threshold of 20 dB to catch degraded quality)
   - Clipping: 5% (higher than operational threshold of 1% to avoid false positives)

5. **Evaluation Periods**: 
   - SNR: 2 periods (10 minutes total) to confirm sustained low quality
   - Clipping: 3 periods (15 minutes total) to avoid transient spike alerts

6. **Metric Periods**: 
   - Real-time metrics: 1 minute for quick detection
   - Event counts: 5 minutes for trend analysis
   - Alarms: 5 minutes to balance responsiveness and stability

## Integration Points

1. **Lambda Function**: Environment variables are read by the audio processor Lambda handler to configure audio quality validation.

2. **CloudWatch Metrics**: Metrics emitted by `QualityMetricsEmitter` class are visualized in the dashboard.

3. **EventBridge**: Quality events emitted by the system can trigger additional workflows or notifications.

4. **SNS Topic**: Alarms send notifications to the existing `audio-transcription-alarms` topic for centralized alerting.

## Deployment Notes

1. **First Deployment**: 
   - Create `config/dev.json` from `config/dev.json.example`
   - Adjust thresholds based on expected audio quality
   - Deploy with `cdk deploy`

2. **Dashboard Access**: 
   - Dashboard available at: CloudWatch Console → Dashboards → `audio-quality-monitoring`
   - Bookmark for quick access during operations

3. **Alarm Configuration**:
   - Subscribe to SNS topic to receive alarm notifications
   - Configure email, SMS, or integration with incident management system

4. **Monitoring**:
   - Monitor dashboard during initial rollout
   - Adjust thresholds based on actual audio quality patterns
   - Review alarm history to tune evaluation periods

## Requirements Addressed

- **Requirement 4.1**: Configuration parameters for SNR threshold, clipping threshold, and echo cancellation sensitivity
- **Requirement 4.2**: Configuration updates applied within 100 milliseconds (via environment variables)
- **Requirement 4.3**: SNR threshold validation (10-40 dB range enforced in code)
- **Requirement 4.4**: Clipping threshold validation (0.1-10% range enforced in code)
- **Requirement 5.1**: Quality metric events emitted to CloudWatch
- **Requirement 5.2**: Metrics published at 1-second intervals (configured via environment)
- **Requirement 5.3**: Quality degradation events with severity levels (via alarms)
