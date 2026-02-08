# Entity Documentation

## Entity 1: The Copier (Brand Book Generator)

**File**: `prompts/copier/copier_system.md` (~104 lines)

### Purpose
Reverse-engineers a reference image into technical specifications. Treats the image as if inspecting browser DevTools.

### When Invoked
**Only when user uploads a reference image.** This means all Copier output implicitly signals `[USER IMAGE]` mode to downstream entities. The output title includes `[USER IMAGE]` as a trigger.

### Output Structure

```markdown
# [USER IMAGE] Technical Design Specification (Brand Book)

## 1. Visual Identity
3 technical adjectives (e.g., "Grid-Locked, High-Contrast, Minimalist")

## 2. Design Style
UI trend classification (e.g., "Swiss Style", "Neo-Brutalism", "Bento Grid")

## 3. Design Essence
One-sentence engineering summary

## 4. Layout DNA
- Grid System (12-column, masonry, etc.)
- Container Width
- Spacing/Gap base unit
- **Density**: Hyper-Dense | Standard | Airy ← TRIGGER FOR DOWNSTREAM
- Whitespace
- Alignment

## 5. Photographic Language
- Border Radius
- Filters/Effects
- Aspect Ratios
- Object Fit
- **Treatment Classification**: Subject Color vs Applied Treatment ← TRIGGER FOR DOWNSTREAM

## 6. Color Palette
Hex codes + usage percentage

## 7. Typography
- Headings:
  - Family, Weight, Case, Letter-spacing, Line-height
  - **Geometry Classification**: Width, Weight Class, Style ← TRIGGER FOR DOWNSTREAM
  - **Relative Scale**: Note if dramatically oversized ← TRIGGER FOR DOWNSTREAM
- Body (family, geometry, weight, size, line-height)
- Special/Display treatments

## 8. Graphic Elements
- Buttons (border, background, radius)
- Strokes/Lines
- Shadows
- Icons
```

### Sensors Added (Triggers for Downstream)

| Sensor | Location | Purpose |
|--------|----------|---------|
| **Density** | Section 4 | Informs spacing decisions based on layout tightness |
| **Treatment Classification** | Section 5 | Enables consistent photo treatment replication |
| **Geometry Classification** | Section 7 | Enables font matching by physical shape |
| **Relative Scale** | Section 7 | Preserves typography proportions |

---

## Entity 2: The Typography Curator

**File**: `prompts/typography_curator/typography_curator_system.md` (~1001 lines)

### Purpose
Selects actual font files from the Wix catalogue to match the Brand Book analysis.

### Resources Available

**48 Curated Presets**: Complete H1-H6, P1-P3 scales ready to use.  
**Full Catalogue**: ~290 fonts for custom scale creation.

### Selection Priority (Current)

```
1. User Request        → Explicit font/style requests override all
2. Industry/Cultural   → Match business type, vibe, tradition
3. Image Reference     → Stylistic influence (not strict mandate)
```

### Output Format

Array format per text role: `[font-slug, weight, size, line-height, letter-spacing]`

```json
{
  "h1": ["neue-haas-grotesk-display-pro", "500", "88px", "1em", "0em"],
  "h2": ["neue-haas-grotesk-display-pro", "500", "66px", "1em", "0em"],
  ...
  "p1": ["neue-haas-grotesk-display-pro", "500", "20px", "1.2em", "0.01em"],
  ...
}
```

### Current Gaps (to be addressed)

1. **No Mode Switch**: Doesn't flip priority for `[USER IMAGE]` mode
2. **No Geometric Matching**: Doesn't prioritize Width (Condensed/Extended) and Weight (Black/Hairline) matching

---

## Entity 3: The Architect (Design Brief Creator)

**File**: `prompts/architect/architect_system.md` (~1035 lines)

### Purpose
The central brain that synthesizes all inputs into a complete design plan.

### Key Responsibilities

1. **Global Brief**: Define site-wide parameters
   - Color Palette (8 roles: Base 1-2, Shade 1,3, Accent 1-4)
   - Typography (selected type scale)
   - Buttons (3 types: Primary, Secondary, Tertiary)
   - Boxes (2 types: Primary, Secondary)
   - Lines (2 styles)
   - Animations (2-3 animation palette)
   - Spacing system
   - Photographic treatment

2. **Local Briefs**: Section-specific instructions for each section type

### Section Types Supported

- Header (Logo + Menu + optional CTA)
- Hero (First impression, H1 usage)
- About (Business story + image)
- List (3-6 items in cards)
- Promotional (CTAs, announcements)
- Contact (Form and/or details)
- Footer (Info + social + copyright)

### Mode Logic (Current State)

**Currently Implemented**:
- Section 6 (Colors): `[USER IMAGE]` prioritizes exact palette
- Section 7 (Typography): `[USER IMAGE]` matches physical shape
- Section 12 (Photos): `[USER IMAGE]` mandates treatment replication

**NOT Yet Implemented**:
- Section 5 (Spacing): No density override for hyper-dense layouts
- Typography Scale: No instruction to preserve massive headers
- Local Briefs: No propagation of specific treatments

### Color System

| Role | Purpose | Contrast Requirement |
|------|---------|---------------------|
| Base 1 | Primary background + Primary Box | Base 1 ↔ Base 2: ≥ 6:1 |
| Base 2 | Primary text + Secondary Box | (same) |
| Shade 1 | Secondary background | Auto-calculated |
| Shade 3 | Secondary text | Auto-calculated |
| Accent 1 | Buttons, links, CTAs | Base 1 ↔ Accent 1: ≥ 4.5:1 |
| Accent 2-4 | Secondary backgrounds | Each ↔ Base 2: ≥ 4.5:1 |

### Button Wiring (Permanent)

| Type | Background | Text | Border |
|------|------------|------|--------|
| Primary | Accent 1 | Base 1 | - |
| Secondary | Base 1 | Accent 1 | Accent 1 |
| Tertiary | Transparent | Accent 1 | - (underline required) |
