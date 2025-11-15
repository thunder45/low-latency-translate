# Task 4: Add sendAudio Route to CDK Configuration - Summary

## Task Description

Added the sendAudio WebSocket route to the CDK infrastructure configuration to enable audio chunks to reach the audio_processor Lambda function from the WebSocket API.

## Task Instructions

The task required:
1. Creating cross-stack references between SessionManagementStack and AudioTranscriptionStack
2. Adding sendAudio route configuration with binary frame support
3. Updating CDK app to create stacks in correct order
4. Verifying route deployment (documented for manual verification)

## Implementation Details

### 4.1 Cross-Stack Reference

**Modified Files:**
- `audio-transcription/infrastructure/stacks/audio_transcription_stack.py`
- `session-management/infrastructure/stacks/session_management_stack.py`

**Changes:**
1. Exposed `audio_processor_function` as public attribute in AudioTranscriptionStack:
   ```python
   self.audio_processor_function = self._create_audio_processor_lambda(lambda_role)
   ```

2. Updated SessionManagementStack constructor to accept audio_transcription_stack parameter:
   ```python
   def __init__(
       self,
       scope: Construct,
       construct_id: str,
       config: dict,
       env_name: str,
       audio_transcription_stack=None,  # New parameter
       **kwargs
   ) -> None:
       super().__init__(scope, construct_id, **kwargs)
       self.audio_transcription_stack = audio_transcription_stack
   ```

### 4.2 sendAudio Route Configuration

**Modified File:**
- `session-management/infrastructure/stacks/session_management_stack.py`

**Changes:**
1. Created Lambda integration for audio_processor function with 60-second timeout:
   ```python
   if self.audio_transcription_stack:
       send_audio_integration = self._create_lambda_integration(
           api,
           self.audio_transcription_stack.audio_processor_function,
           "SendAudioIntegration",
           timeout_ms=60000  # 60 seconds for audio processing
       )
       # Configure binary frame support
       send_audio_integration.content_handling_strategy = "CONVERT_TO_BINARY"
   ```

2. Created sendAudio route:
   ```python
   send_audio_route = apigwv2.CfnRoute(
       self,
       "SendAudioRoute",
       api_id=api.ref,
       route_key="sendAudio",
       target=f"integrations/{send_audio_integration.ref}",
   )
   ```

3. Added route as deployment dependency:
   ```python
   if send_audio_route:
       deployment.add_dependency(send_audio_route)
   ```

**Key Configuration:**
- Route key: `sendAudio`
- Integration timeout: 60 seconds (60000ms)
- Content handling: `CONVERT_TO_BINARY` for binary WebSocket frames
- Target: audio_processor Lambda function from AudioTranscriptionStack

### 4.3 CDK App Update

**Modified File:**
- `session-management/infrastructure/app.py`

**Changes:**
1. Added import path for AudioTranscriptionStack:
   ```python
   audio_transcription_infra_path = os.path.join(
       os.path.dirname(__file__),
       "../../audio-transcription/infrastructure"
   )
   sys.path.insert(0, audio_transcription_infra_path)
   ```

2. Created AudioTranscriptionStack first:
   ```python
   audio_transcription_stack = AudioTranscriptionStack(
       app,
       f"AudioTranscription-{env_name}",
       env=env
   )
   ```

3. Passed audio_transcription_stack to SessionManagementStack:
   ```python
   session_management_stack = SessionManagementStack(
       app,
       f"SessionManagement-{env_name}",
       env=env,
       config=config,
       env_name=env_name,
       audio_transcription_stack=audio_transcription_stack
   )
   ```

4. Added explicit stack dependency:
   ```python
   if audio_transcription_stack:
       session_management_stack.add_dependency(audio_transcription_stack)
   ```

**Graceful Degradation:**
The implementation includes graceful handling if AudioTranscriptionStack is not available:
- Prints warning message
- SessionManagementStack creates without sendAudio route
- Other routes continue to function normally

### 4.4 Verification Steps (Manual)

Since actual AWS deployment cannot be performed in this environment, the following verification steps should be performed during deployment:

#### Pre-Deployment Verification

1. **Syntax Check** (✅ Completed):
   ```bash
   python3 -m py_compile session-management/infrastructure/app.py
   python3 -m py_compile session-management/infrastructure/stacks/session_management_stack.py
   python3 -m py_compile audio-transcription/infrastructure/app.py
   python3 -m py_compile audio-transcription/infrastructure/stacks/audio_transcription_stack.py
   ```
   Result: All files compile without errors

2. **CDK Synth** (To be performed):
   ```bash
   cd session-management/infrastructure
   cdk synth --context env=dev
   ```
   Expected: CloudFormation template generated successfully with sendAudio route

3. **Template Inspection** (To be performed):
   Review generated CloudFormation template for:
   - SendAudioRoute resource with route_key="sendAudio"
   - SendAudioIntegration resource with:
     - integration_type="AWS_PROXY"
     - timeout_in_millis=60000
     - content_handling_strategy="CONVERT_TO_BINARY"
   - Lambda permission for API Gateway to invoke audio_processor

#### Deployment Verification

1. **Deploy to Dev Environment**:
   ```bash
   cd session-management/infrastructure
   cdk deploy --context env=dev --all
   ```

2. **Verify in API Gateway Console**:
   - Navigate to API Gateway → WebSocket APIs
   - Select session-websocket-api-dev
   - Go to Routes section
   - Confirm sendAudio route exists with:
     - Route key: sendAudio
     - Integration: Lambda (audio-processor)
     - Integration timeout: 60000ms

3. **Test Route with Sample Message**:
   ```bash
   # Connect to WebSocket
   wscat -c "wss://<api-id>.execute-api.<region>.amazonaws.com/prod?token=<jwt-token>"
   
   # Send test message
   {"action": "sendAudio", "data": "<base64-encoded-audio>"}
   ```
   Expected: audio_processor Lambda invoked successfully

4. **Verify Lambda Invocation**:
   - Check CloudWatch Logs for audio-processor function
   - Confirm function received WebSocket event
   - Verify binary data handling works correctly

5. **Monitor CloudWatch Metrics**:
   - Check AudioChunksReceived metric
   - Verify no integration errors
   - Confirm latency within acceptable range (<60s)

#### Rollback Plan

If issues occur during deployment:
1. Revert CDK changes:
   ```bash
   git revert <commit-hash>
   ```

2. Redeploy previous version:
   ```bash
   cdk deploy --context env=dev --all
   ```

3. Verify previous routes still functional

## Requirements Addressed

- **Requirement 4**: Add sendAudio route to CDK configuration
- **Requirement 4.1**: Import AudioTranscriptionStack in session_management_stack.py
- **Requirement 4.2**: Accept audio_transcription_stack parameter in constructor
- **Requirement 4.3**: Create Lambda integration for audio_processor function
- **Requirement 4.4**: Configure content_handling_strategy="CONVERT_TO_BINARY"
- **Requirement 4.5**: Modify infrastructure/app.py to create stacks in correct order
- **Requirement 12.2**: Verify sendAudio route appears in API Gateway console (documented for manual verification)

## Testing

### Syntax Validation
✅ All Python files compile without errors

### Integration Points
The sendAudio route integrates with:
1. **audio_processor Lambda** (audio-transcription component)
   - Receives binary audio chunks via WebSocket
   - Processes audio through Transcribe streaming
   - Forwards transcriptions to Translation Pipeline

2. **WebSocket API** (session-management component)
   - Routes sendAudio messages to audio_processor
   - Handles binary frame conversion
   - Manages connection lifecycle

### Expected Behavior
When a speaker sends audio:
1. Frontend sends binary WebSocket message with action="sendAudio"
2. API Gateway routes to sendAudio route
3. Binary data converted and passed to audio_processor Lambda
4. Lambda processes audio chunk through Transcribe
5. Transcription forwarded to Translation Pipeline
6. Translated audio broadcast to listeners

## Files Modified

1. `audio-transcription/infrastructure/stacks/audio_transcription_stack.py`
   - Exposed audio_processor_function as public attribute

2. `session-management/infrastructure/stacks/session_management_stack.py`
   - Added audio_transcription_stack parameter to constructor
   - Created sendAudio route with binary frame support
   - Added Lambda integration with 60-second timeout

3. `session-management/infrastructure/app.py`
   - Added AudioTranscriptionStack import
   - Created AudioTranscriptionStack before SessionManagementStack
   - Passed stack reference to SessionManagementStack
   - Added explicit stack dependency

## Next Steps

1. **Deploy to Dev Environment**:
   - Run CDK synth to verify CloudFormation template
   - Deploy both stacks to dev environment
   - Verify sendAudio route in API Gateway console

2. **Integration Testing**:
   - Test audio chunk sending via WebSocket
   - Verify audio_processor Lambda receives data
   - Confirm binary data handling works correctly
   - Monitor CloudWatch metrics

3. **Documentation Updates**:
   - Update deployment guide with new stack dependencies
   - Document sendAudio route in API documentation
   - Add troubleshooting guide for route issues

4. **Continue with Phase 5**:
   - Proceed to Task 5: Integrate emotion detection with audio processing
   - Emotion data will be included in audio processing flow
   - EmotionDynamicsOrchestrator will be integrated with audio_processor

## Notes

- The implementation uses graceful degradation: if AudioTranscriptionStack is not available, SessionManagementStack creates without sendAudio route
- Binary frame support is critical for efficient audio transmission
- 60-second timeout accommodates audio processing and Transcribe streaming
- Cross-stack dependencies ensure proper creation order
- The sendAudio route completes the WebSocket audio integration foundation

## Success Criteria

✅ Cross-stack reference created successfully
✅ sendAudio route configuration added with binary support
✅ CDK app updated to create stacks in correct order
✅ Python syntax validation passed
⏳ Route deployment verification (requires AWS deployment)

The infrastructure changes are complete and ready for deployment. Manual verification steps are documented above for execution during actual AWS deployment.
