# Testing & Versioning Guide

## Quick Start

```bash
# Run the Copier prompt
python pipeline_test.py run copier

# Run Copier → Curator chain
python pipeline_test.py chain copier curator

# Run a predefined scenario
python pipeline_test.py scenario user_image_flow

# Compare last two runs of a prompt
python pipeline_test.py diff copier

# List all saved results
python pipeline_test.py list
```

## Pipeline Test Runner

The `pipeline_test.py` script provides:

### Commands

| Command | Description |
|---------|-------------|
| `run <prompt>` | Run a single prompt |
| `chain <p1> <p2> ...` | Run prompts in sequence, passing outputs as inputs |
| `scenario <name>` | Run a predefined test scenario |
| `diff <prompt>` | Compare last two results |
| `list` | List all saved results |

### Configuring Prompts

Edit `PROMPTS` dict in `pipeline_test.py`:

```python
PROMPTS = {
    "copier": {
        "id": "your-prompt-id-here",
        "name": "Brand Book Generator",
        "output_key": "image_brandbook"  # Key when passing to next stage
    },
    ...
}
```

### Chaining Outputs

When running a chain, the output from each stage is automatically passed to the next stage using the `output_key`:

```
copier output → image_brandbook param → curator
curator output → editor_typography_selection param → architect
```

### Results Storage

Results are saved to `test_results/` (git-ignored):
- `{prompt}_{timestamp}.json` - Full response with params
- `{prompt}_{timestamp}.md` - Human-readable output

---

## Git Workflow for Prompts

### What Gets Versioned

```
✅ Versioned (committed to git):
   prompts/           # All prompt files
   docs/              # Documentation
   pipeline_test.py   # Test runner
   
❌ Not versioned (git-ignored):
   test_results/      # Test outputs
   config.json        # Secrets/credentials
   venv/              # Dependencies
```

### Workflow: Making Changes

```bash
# 1. Create a branch for your change
git checkout -b feature/improve-density-sensor

# 2. Edit the prompt
# (make changes to prompts/copier/copier_system.md)

# 3. Test the change
python pipeline_test.py run copier

# 4. Compare with previous run (if needed)
python pipeline_test.py diff copier

# 5. Happy? Commit the prompt change
git add prompts/
git commit -m "copier: improve density sensor terminology"

# 6. Push and create PR (or merge to main)
git push -u origin feature/improve-density-sensor
```

### Workflow: Comparing Versions

```bash
# See what changed in a prompt file
git diff HEAD~1 prompts/copier/copier_system.md

# See all prompt changes in last 5 commits
git log --oneline -5 -- prompts/

# Compare current branch to main
git diff main -- prompts/

# Restore a previous version of a prompt
git checkout HEAD~1 -- prompts/copier/copier_system.md
```

### Workflow: Reverting a Bad Change

```bash
# Option 1: Revert a specific commit
git revert <commit-hash>

# Option 2: Restore file from specific commit
git checkout <commit-hash> -- prompts/copier/copier_system.md

# Option 3: Reset to previous state (careful!)
git reset --hard HEAD~1
```

---

## Testing Scenarios

### Predefined Scenarios

Edit `SCENARIOS` in `pipeline_test.py`:

```python
SCENARIOS = {
    "user_image_flow": {
        "description": "Test USER IMAGE mode: Copier → Curator",
        "chain": ["copier", "curator"],
        "base_params": {
            "editor_business_type": "Engineering Company",
            "editor_site_description": "Industrial engineering services"
        }
    }
}
```

### Creating New Scenarios

1. Define the chain of prompts to run
2. Set base params that apply to all stages
3. Run with `python pipeline_test.py scenario <name>`

---

## Evaluation Checklist

When testing prompt changes, check:

### Copier
- [ ] `[USER IMAGE]` label in title?
- [ ] Density classification present?
- [ ] Treatment classification correct?
- [ ] Geometry classification for fonts?
- [ ] Relative scale noted?

### Curator
- [ ] Fonts match Brand Book geometry?
- [ ] Priority flip working for [USER IMAGE]?
- [ ] Diverse selections (not all "safe" fonts)?

### Architect
- [ ] Colors match Brand Book for [USER IMAGE]?
- [ ] Typography selection honored?
- [ ] Treatments propagated to local briefs?

---

## Tips

1. **Run tests before committing** - Always test your prompt changes
2. **Small commits** - One logical change per commit
3. **Descriptive messages** - `copier: add treatment classification sensor`
4. **Branch for experiments** - Don't experiment on main
5. **Compare outputs** - Use `diff` command to spot regressions
