# Example Quality Standards — V6-D3#3

## Requirements for All Examples

1. **Complete**: Runnable without modification
2. **Minimal**: Demonstrates exactly one concept
3. **Commented**: Key lines explained
4. **Tested**: Example code is tested in CI

## Example Template
```python
"""
Title: Brief description
Prerequisites: pip install ww-bridge
"""
# Step 1: Import and setup
from ww_bridge import GeminiBridge

# Step 2: Configure (explain each option)
bridge = GeminiBridge(verbose=True)

# Step 3: Execute (explain what's happening)
result = bridge.run("Your query here")
print(result)
```

## Review Checklist
- [ ] Example runs end-to-end
- [ ] No undefined variables
- [ ] Output matches documentation
- [ ] Error cases documented
- [ ] Requirements specified
