# Task 4: Implement SSML Generator

## Task Description
Implemented SSML Generator to create emotion-aware Speech Synthesis Markup Language from translated text and emotion dynamics.

## Task Instructions
Create SSML Generator with the following capabilities:
- XML escaping utility for reserved characters (&, <, >, ", ')
- Dynamics-to-SSML mapping for speaking rate (WPM to prosody rate)
- Dynamics-to-SSML mapping for volume level (to prosody volume)
- Emotion-to-emphasis mapping based on emotion type and intensity
- Complete SSML template generation with nested prosody tags

## Task Tests
```bash
python -m pytest tests/unit/test_ssml_generator.py -v
```

**Results**: 32 tests passed

**Test Coverage**:
- XML escaping: 6 tests (ampersand, less than, greater than, quotes, apostrophe, multiple chars)
- Rate mapping: 4 tests (slow, medium, fast, x-fast)
- Volume mapping: 5 tests (whisper, soft, normal, loud, unknown default)
- Emotion emphasis: 8 tests (angry, excited, surprised, sad, fearful, neutral, happy, intensity thresholds)
- Complete SSML generation: 9 tests (various emotion/rate/volume combinations, special characters, structure validation)

## Task Solution

### Files Created

1. **shared/models/emotion_dynamics.py**
   - Created `EmotionDynamics` dataclass to represent detected emotion and speaking characteristics
   - Includes validation for intensity (0.0-1.0), rate_wpm (positive), and volume_level (valid values)

2. **shared/services/ssml_generator.py**
   - Implemented `SSMLGenerator` class with complete SSML generation logic
   - Key methods:
     - `generate_ssml()`: Main entry point for SSML generation
     - `_escape_xml()`: Escapes XML reserved characters using html.escape()
     - `_map_rate_to_ssml()`: Maps WPM ranges to SSML rate values (slow/medium/fast/x-fast)
     - `_map_volume_to_ssml()`: Maps volume levels to SSML volume values (x-soft/soft/medium/loud)
     - `_apply_emotion_emphasis()`: Applies emphasis tags based on emotion type and intensity

3. **tests/unit/test_ssml_generator.py**
   - Comprehensive test suite with 32 tests covering all functionality
   - Tests XML escaping, rate/volume mapping, emotion emphasis, and complete SSML generation

### Implementation Details

**Rate Mapping**:
- 0-120 WPM → "slow"
- 120-170 WPM → "medium"
- 170-200 WPM → "fast"
- 200+ WPM → "x-fast"

**Volume Mapping**:
- "whisper" → "x-soft"
- "soft" → "soft"
- "normal" → "medium"
- "loud" → "loud"

**Emotion Emphasis**:
- Strong emphasis: angry/excited/surprised with intensity > 0.7
- Pauses: sad/fearful emotions get 300ms break before text
- No emphasis: neutral, happy, or low-intensity emotions

**SSML Structure**:
```xml
<speak>
  <prosody rate="{rate}">
    <prosody volume="{volume}">
      {emotion_enhanced_text}
    </prosody>
  </prosody>
</speak>
```

### Key Design Decisions

1. **XML Escaping**: Used Python's built-in `html.escape()` with `quote=True` to handle all XML reserved characters safely

2. **Nested Prosody Tags**: Applied rate and volume as separate nested prosody tags for maximum compatibility with AWS Polly

3. **Emotion Emphasis**: Implemented threshold-based emphasis (intensity > 0.7) to avoid over-emphasizing subtle emotions

4. **Pause for Sad/Fearful**: Added 300ms break before text for sad/fearful emotions to create natural pauses

5. **Validation**: Added input validation in EmotionDynamics dataclass to catch invalid values early

### Requirements Addressed

- **Requirement 3.1**: Generate SSML markup based on detected emotion, volume level, and speaking rate ✓
- **Requirement 3.2**: Apply strong emphasis for angry/excited/surprised with intensity > 0.7 ✓
- **Requirement 3.3**: Apply prosody rate="fast" for fast speaking rate (170-200 WPM) ✓
- **Requirement 3.4**: Apply prosody volume="loud" for loud volume level ✓
- **Requirement 3.5**: Escape XML reserved characters before generating SSML ✓
