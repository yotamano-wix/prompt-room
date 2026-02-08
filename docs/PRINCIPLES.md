# Prompt Engineering Principles

## Core Rules for This Repository

### 1. Flexibility Over Specificity

**Never hardcode specific values as rules.** The pipeline must remain agnostic and adaptable to any design.

| ❌ Bad (Too Specific) | ✅ Good (Principle-Based) |
|----------------------|---------------------------|
| "Allow 0px gaps when dense" | "Replicate the density characteristics reported in the Brand Book" |
| "Use 180px for massive headers" | "Preserve the relative scale and visual proportion of typography" |
| "Apply blue duotone filter" | "Apply the specific treatment named in the Brand Book" |

### 2. Principle Hierarchy

When writing prompt instructions:

1. **State the principle** (what to achieve)
2. **Reference the data source** (where to get the values)
3. **Avoid example values** in the rule itself

**Example**:
```markdown
❌ "If headers are 180px, keep them at 180px"
✅ "Preserve the relative typographic scale described in the Brand Book"
```

### 3. Let Analysis Drive Values

The Copier analyzes the image and outputs specific values. Downstream entities (Curator, Architect) should:
- **Read** those values from the Brand Book
- **Apply** them as specified
- **NOT** have their own hardcoded thresholds

### 4. Mode Logic Belongs in Principles, Not Values

The `[USER IMAGE]` vs `[INTERNAL IMAGE]` distinction should change **priorities and behaviors**, not inject specific CSS values.

**Example**:
```markdown
❌ "[USER IMAGE]: Use 0px gaps, 180px headers, blue duotone"
✅ "[USER IMAGE]: Prioritize exact replication of Brand Book specifications over business-type conventions"
```

---

## Why This Matters

1. **Scalability**: The same prompts work for minimalist AND maximalist designs
2. **Maintainability**: No need to update prompts when new edge cases appear
3. **Accuracy**: Values come from actual image analysis, not prompt assumptions
4. **Debugging**: If output is wrong, fix the analysis (Copier), not the rules

---

## Applying This to Changes

When modifying prompts in this repo:

1. Ask: "Am I adding a principle or a specific value?"
2. If adding a value, ask: "Should this come from Brand Book analysis instead?"
3. Keep examples in documentation, not in prompt rules
4. Test with diverse reference images, not just the case that triggered the change
