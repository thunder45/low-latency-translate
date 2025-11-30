# Optional Features Reintegration Plan

## Status: Phase 4 Complete Without Optional Features

**Date:** November 30, 2025  
**Phase 4 Core:** ✅ WORKING (Kinesis + Transcribe + Translate + TTS)  
**Disabled Features:** Emotion Detection, Audio Quality Analysis

---

## Why Features Were Disabled

Lambda has a **250MB uncompressed package limit**. The optional features require:
- **scipy** (40MB) - Signal processing
- **librosa** (60MB) - Audio analysis  
- **scikit-learn** (30MB) - Machine learning
- **numba/llvmlite** (80MB) - JIT compilation
- **Total: 210MB+** just for these dependencies

**Solution:** Temporarily disabled to get Phase 4 (Kinesis) working. Core translation works without them.

---

## Reintegration Approaches

### Option 1: Separate Lambda for Audio Quality (Recommended)

Create a dedicated Lambda for emotion/quality processing:

**Benefits:**
- Clean separation of concerns
- Each Lambda stays under 250MB
- Can scale independently
- Easy to maintain

**Architecture:**
```
connection_handler → Kinesis → audio_processor (transcribe/translate)
                              ↘ audio_quality_processor (emotion/quality)
```

**Steps:**
1. Create `audio-transcription/lambda/audio_quality_processor/`
2. Move emotion/quality code there
3. Add scipy/librosa to its requirements.txt
4. Invoke from audio_processor after transcription
5. Deploy as separate Lambda

**Time:** 2-3 hours

---

### Option 2: Container Image Lambda

Use Docker container image (10GB limit instead of 250MB):

**Benefits:**
- All features in one Lambda
- Simple architecture
- No size constraints

**Drawbacks:**
- Cold start slower (2-3s vs 500ms)
- More complex deployment
- Requires ECR repository

**Steps:**
1. Create Dockerfile in `audio-transcription/lambda/audio_processor/`
2. Base image: `public.ecr.aws/lambda/python:3.11`
3. Install all dependencies
4. Push to ECR
5. Update CDK to use container image

**Time:** 1-2 hours

---

### Option 3: Lambda Extensions (Advanced)

Use Lambda Extensions for background processing:

**Benefits:**
- Runs alongside main Lambda
- Separate process and memory
- Can have own dependencies

**Drawbacks:**
- Complex architecture
- Limited to 10 extensions
- Still counts toward total size

**Time:** 4-6 hours

---

## Recommended Path: Option 1 (Separate Lambda)

### Implementation Plan

#### Step 1: Create Audio Quality Lambda (1 hour)
```bash
cd audio-transcription/lambda
mkdir -p audio_quality_processor
cp -r ../emotion_dynamics audio_quality_processor/
cp -r ../audio_quality audio_quality_processor/
cp -r ../shared audio_quality_processor/

# Create handler
cat > audio_quality_processor/handler.py << 'EOF'
import json
import boto3
import numpy as np
from emotion_dynamics.orchestrator import AudioDynamicsOrchestrator
from audio_quality.analyzers.quality_analyzer import AudioQualityAnalyzer

def lambda_handler(event, context):
    # Process audio quality and emotion
    # Return results
    pass
EOF

# Create requirements.txt
cat > audio_quality_processor/requirements.txt << 'EOF'
numpy>=1.24.0
scipy>=1.11.0
librosa>=0.10.0
soundfile>=0.12.0
boto3>=1.28.0
EOF
```

#### Step 2: Add to CDK Stack (30 min)
```python
# In audio_transcription_stack.py

self.audio_quality_processor = lambda_.Function(
    self,
    'AudioQualityProcessor',
    function_name='audio-quality-processor',
    runtime=lambda_.Runtime.PYTHON_3_11,
    handler='handler.lambda_handler',
    code=lambda_.Code.from_asset(
        audio_quality_path,
        bundling=BundlingOptions(...)  # Install scipy/librosa
    ),
    memory_size=1024,  # More memory for scipy
    timeout=Duration.seconds(30),
)
```

#### Step 3: Integrate (30 min)
In `audio_processor/handler.py`, after transcription:
```python
# After getting transcript, invoke quality processor
quality_client = boto3.client('lambda')
quality_response = quality_client.invoke(
    FunctionName='audio-quality-processor',
    InvocationType='Event',  # Async
    Payload=json.dumps({
        'sessionId': session_id,
        'audioData': pcm_data.hex(),
        'transcript': transcript
    })
)
```

#### Step 4: Deploy (15 min)
```bash
cd audio-transcription
make deploy-dev
```

---

## When to Reintegrate

### Immediate (if needed):
- Users complaining about missing emotion in TTS
- Audio quality issues need detection

### Can wait:
- Core translation working well
- Users satisfied with current quality
- Focus on other features first

**Recommendation:** Wait 1-2 weeks, get Phase 4 stable, then add back if users request emotion features.

---

## Restoring Features: Quick Guide

### If Using Option 1 (Separate Lambda):
1. Follow "Implementation Plan" above
2. Deploy new Lambda
3. Update audio_processor to invoke it
4. Test end-to-end

### If Using Option 2 (Container Image):
1. Create Dockerfile
2. Build and push to ECR
3. Update CDK to use container
4. Uncomment imports in handler.py
5. Deploy

### If Just Re-enabling (not recommended):
1. Uncomment imports in `audio_processor/handler.py`
2. Add scipy/librosa to `requirements.txt`
3. Update Layer to include emotion_dynamics/audio_quality
4. Deploy (will likely fail with 250MB limit again)

---

## Testing After Reintegration

```bash
# 1. Test emotion extraction
aws lambda invoke \
  --function-name audio-quality-processor \
  --payload '{"sessionId":"test","audioData":"..."}' \
  /tmp/quality-test.json

# 2. Test end-to-end
cd frontend-client-apps/speaker-app && npm run dev
# Speak with varying volume/speed
# Check TTS has proper emotion (prosody tags)

# 3. Verify metrics
aws cloudwatch get-metric-statistics \
  --namespace AudioTranscription/EmotionDetection \
  --metric-name EmotionExtractionLatency \
  --start-time $(date -u -v-5M +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

---

## Cost Impact

### Current (Without Emotion/Quality):
- Lambda size: ~50MB
- Execution time: 5-7s
- Memory: 512MB

### With Option 1 (Separate Lambda):
- Main Lambda: ~50MB
- Quality Lambda: ~200MB
- Execution time: 5-7s (main) + 1-2s (quality, async)
- Memory: 512MB (main) + 1024MB (quality)
- Cost increase: ~15% (quality Lambda runs async)

### With Option 2 (Container):
- Lambda size: 500MB (container)
- Cold start: 2-3s (vs 500ms)
- Execution time: 5-7s
- Cost increase: ~20% (higher cold start frequency)

**Recommendation:** Option 1 is most cost-effective and maintains performance.

---

## Files Modified for Temporary Disablement

### Phase 4 Changes (Reverted When Re-enabling):
1. `audio-transcription/lambda/audio_processor/handler.py`
   - Lines 55-79: Commented imports
   - Lines 81-88: Added placeholder classes
   - Lines 91-96: Set globals to None

2. `audio-transcription/lambda/audio_processor/requirements.txt`
   - Removed: scipy, librosa, soundfile
   - Note added explaining temporary removal

3. `audio-transcription/layer/python/`
   - Excluded: emotion_dynamics, audio_quality
   - Layer v3: Only shared module (157KB)

---

## Rollback Plan

If reintegration fails:
1. Keep features disabled (current working state)
2. Revert handler.py changes
3. Redeploy
4. No impact on Phase 4 core functionality

---

## Support

For questions about reintegration:
1. Check this document first
2. Review CHECKPOINT_PHASE4_COMPLETE.md
3. See emotion_dynamics/README.md
4. See audio_quality/README.md

**Current Status:** Core Phase 4 working, optional features documented for future addition.
