# Pipeline Architecture

## Overview

The design pipeline generates websites through a linear three-stage process. Each stage has a specialized LLM prompt that performs one role in the chain.

```
INPUT                    STAGE 1              STAGE 2              STAGE 3              OUTPUT
─────                    ───────              ───────              ───────              ──────
Reference Image    ───▶  COPIER         ───▶  CURATOR        ───▶  ARCHITECT     ───▶  Design Brief
Business Context         (Brand Book)         (Typography)         (Global+Local)       (JSON)
```

## Data Flow

### Input
- **Reference Image**: Visual inspiration (internal template OR user-uploaded)
- **Business Context**: Type, description, name
- **User Request**: Specific styling requirements
- **Site Structure**: Section list to generate

### Stage 1: Copier (Brand Book Generator)

**Role**: The Sensor. Inspects the reference image and extracts raw technical DNA.

**Input**: Reference image  
**Output**: Brand Book with:
- Visual Identity (3 technical adjectives)
- Design Style classification
- Layout DNA (grid, spacing, alignment)
- Color Palette (hex codes + usage %)
- Typography specs (family, weight, sizing)
- Photographic treatments (filters, crops, effects)
- Component styling (buttons, shadows, radii)

**Key Constraint**: Outputs CSS-ready values. No vague terms like "large" or "colorful."

### Stage 2: Typography Curator

**Role**: The Librarian. Selects actual font files from the Wix font catalogue.

**Input**: Brand Book + Business Context  
**Output**: 1-3 type scale selections from:
- 48 curated presets (ready-to-use complete scales)
- Full font catalogue (~290 fonts) for custom scales

**Selection Priority** (current):
1. User Request (explicit font requests)
2. Industry & Cultural Fit
3. Image Reference (stylistic influence)

### Stage 3: Architect (Design Brief Creator)

**Role**: The Brain. Synthesizes everything into actionable design instructions.

**Input**: Brand Book + Typography Selection + Business Context + Site Structure  
**Output**: 
- **Global Brief**: Site-wide parameters (colors, typography, buttons, boxes, lines, animations, spacing)
- **Local Briefs**: Section-specific instructions for each section in the site structure

**Key Responsibility**: Ensures all parallel section generators produce visually cohesive results.

## Mode Detection

The mode is determined by **whether the Copier was invoked**:

- **Copier runs** → `[USER IMAGE]` mode (user uploaded a reference)
- **Copier doesn't run** → `[INTERNAL IMAGE]` mode (system-provided template)

The Copier's output includes `[USER IMAGE]` in its title, signaling downstream entities (Curator, Architect) to apply Digital Twin behavior.

### Mode Behavioral Matrix

| Aspect | INTERNAL IMAGE | USER IMAGE |
|--------|----------------|------------|
| Colors | Inspired by, never copied | Exact palette from Brand Book |
| Typography | Best business fit | Match physical geometry first |
| Spacing | Standard minimums (20px) | Replicate density if dense |
| Photo Treatment | Appropriate for business | Mandatory replication |

## Output Contract

The Architect outputs JSON that feeds into parallel section generators:

```json
{
  "global": {
    "siteIdentity": "...",
    "visualProfile": "...",
    "designStyle": "...",
    "colorPalette": { ... },
    "typography": { ... },
    "buttons": { ... },
    "boxes": { ... },
    "lines": { ... },
    "animations": { ... },
    "spacing": { ... },
    "photographicTreatment": { ... }
  },
  "sections": {
    "header": { ... },
    "hero": { ... },
    "about": { ... },
    ...
  }
}
```
