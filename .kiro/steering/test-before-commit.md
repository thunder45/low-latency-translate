---
inclusion: always
---

# Test-Driven Task Workflow

## Pre-Task Requirements

Before starting any task:
1. Run all tests
2. Verify all tests pass with zero warnings
3. If tests fail, resolve issues before proceeding

## Post-Task Requirements

After completing any task:
1. Run all tests again to ensure no regressions
2. All tests must pass with zero warnings
3. Generate task summary documentation in `docs/TASK_<number>_SUMMARY.md`
4. Update root-level documentation as needed:
   - `README.md` - Add task summary links, update architecture if changed
   - `OVERVIEW.md` - Update status, features, or current state
   - `PROJECT_STRUCTURE.md` - Update file tree if files added/removed
   - `QUICKSTART.md` - Update if setup/deployment steps changed
   - `DEPLOYMENT.md` - Update if deployment procedures changed
5. Update `validate_structure.py` if new required files were added

## Task Summary Documentation

Create `<root_feature_folder>/docs/TASK_<number>_SUMMARY.md` (where "root_feature_folder" is something like "session-management") with:

### Required Sections

**Task Description**: Brief 1-2 sentence overview

**Task Instructions**: Detailed requirements and acceptance criteria

**Task Tests**: 
- List of test commands executed
- Test results (pass/fail counts)
- Coverage metrics if applicable

**Task Solution**:
- Key implementation decisions
- Code changes summary
- Files modified/created

### Example Structure

```markdown
# Task 15: Implement Feature X

## Task Description
Brief description of what was implemented.

## Task Instructions
Detailed requirements from specification.

## Task Tests
- `pytest tests/test_feature_x.py` - 12 passed
- `pytest tests/integration/` - 8 passed
- Coverage: 85%

## Task Solution
- Created `shared/services/feature_x.py`
- Modified `lambda/handler.py` to integrate feature
- Added validation logic for edge cases
```

## Workflow Summary

1. **Before**: Run tests, ensure clean baseline
2. **During**: Implement changes following TDD principles
3. **After**: Run tests, verify no regressions, document in `docs/TASK_<number>_SUMMARY.md`

