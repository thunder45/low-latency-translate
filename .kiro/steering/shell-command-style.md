---
inclusion: always
---

# Shell Command Style Guide

## ZSH Command Quoting

When providing shell commands for ZSH (the user's shell), always use single quotes instead of double quotes unless variable expansion is explicitly needed.

### Rules

1. **Default to single quotes** for string literals in commands
2. **Use double quotes only when**:
   - Variable expansion is required (e.g., `"$HOME"`, `"${VAR}"`)
   - Command substitution is needed (e.g., `"$(command)"`)
   - Escape sequences are necessary

### Examples

✅ **Correct** (single quotes):
```bash
echo 'Hello, World!'
grep 'pattern' file.txt
find . -name '*.py'
aws s3 ls 's3://bucket-name'
```

❌ **Avoid** (double quotes when not needed):
```bash
echo "Hello, World!"
grep "pattern" file.txt
find . -name "*.py"
```

✅ **Correct** (double quotes when needed):
```bash
echo "Current directory: $PWD"
echo "User: ${USER}"
aws s3 cp file.txt "s3://bucket-${ENV}"
```

### Rationale

- Single quotes prevent unexpected variable expansion
- More predictable behavior in ZSH
- Clearer intent when variables are actually needed
- Follows ZSH best practices

### Application

Apply this rule to:
- Command examples in documentation
- Makefile commands
- Script examples
- README instructions
- Deployment guides
