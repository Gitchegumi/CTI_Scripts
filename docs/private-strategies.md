# Private Strategy Injection

The CTI_Scripts repo is public, but your profitable strategies don't have to be.

## Excluded from Git

The following patterns are excluded from version control (see `.gitignore`):

- `strategies/private/` — Private strategy directory
- `*.private.py` — Private Python strategy files
- `*.private.json` — Private strategy configs

## Loading Private Strategies

### Option 1: Volume Mount (Docker)

```bash
# Mount your local strategies directory
docker run -v ~/my-strategies:/app/strategies/private \
  ghcr.io/gitchegumi/cti-scripts:latest
```

### Option 2: Environment Variable (Base64)

```bash
# Encode your strategy
export STRATEGY_CODE=$(base64 -w0 ~/my-strategies/secret_strat.py)

# In container, decode and write
python -c "
import os, base64
with open('/app/strategies/private/strat.py', 'w') as f:
    f.write(base64.b64decode(os.environ['STRATEGY_CODE']).decode())
"
```

### Option 3: GitHub Secret + Workflow

```yaml
# In your workflow, inject from secret
- name: Inject private strategy
  run: |
    echo "${{ secrets.PRIVATE_STRATEGY }}" | base64 -d > strategies/private/strat.py
  env:
    PRIVATE_STRATEGY: ${{ secrets.PRIVATE_STRATEGY }}
```

## Strategy Loader Pattern

Add to your bot initialization:

```python
import os
from pathlib import Path

def load_private_strategies():
    private_dir = Path("strategies/private")
    if not private_dir.exists():
        return []
    
    strategies = []
    for file in private_dir.glob("*.py"):
        # Dynamic import of private strategies
        spec = importlib.util.spec_from_file_location(file.stem, file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, 'STRATEGY'):
            strategies.append(module.STRATEGY)
    return strategies
```

## Directory Structure

```
CTI_Scripts/
├── strategies/
│   ├── __init__.py
│   ├── public/
│   │   └── basic_momentum.py     # Public, in git
│   └── private/
│       └── my_profit_strat.py    # Private, .gitignored
├── src/
│   └── tradegumi/
│       └── bot.py                # Loads from both dirs
└── docs/
    └── private-strategies.md     # This file
```

## Keeping Secrets

1. **Never commit** files matching `*.private.py` or `*.private.json`
2. **Use GitHub Secrets** for CI/CD injection
3. **Use Docker volumes** for local development
4. **Document the interface** your strategies must implement (without revealing the logic)
