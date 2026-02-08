# Prompt Room - LLM Quick Start Guide

## What Is This?

This repository contains prompts for a **Wix website generation pipeline**. The system takes a reference image + business context and produces a complete website design brief.

## Pipeline Summary (30-Second Version)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   COPIER    │───▶│   CURATOR   │───▶│  ARCHITECT  │
│ (Sensor)    │    │ (Librarian) │    │   (Brain)   │
└─────────────┘    └─────────────┘    └─────────────┘
      │                  │                   │
      ▼                  ▼                   ▼
  Brand Book        Typography          Design Brief
  (Technical        Selection           (Global +
   DNA)             (Font Files)         Local)
```

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `prompts/copier/copier_system.md` | Extracts technical specs from reference image | ~104 |
| `prompts/typography_curator/typography_curator_system.md` | Selects fonts from catalogue | ~1001 |
| `prompts/architect/architect_system.md` | Creates complete design briefs | ~1035 |

## Two Operating Modes

The system has two modes based on image source:

| Mode | When | Behavior |
|------|------|----------|
| `[INTERNAL IMAGE]` | System-provided reference | Business context > Image style. Safe, expected results. |
| `[USER IMAGE]` | User-uploaded reference | **Digital Twin mode.** Exact replication of reference style. |

## Current Status

See [`ROADMAP.md`](./ROADMAP.md) for planned changes to implement strict USER IMAGE mode.

## Quick Links

- [Pipeline Architecture](./PIPELINE.md) - Detailed flow and data contracts
- [Entity Documentation](./ENTITIES.md) - Deep dive into each prompt
- [Prompt Principles](./PRINCIPLES.md) - Rules for writing/modifying prompts
- [Testing & Versioning](./TESTING.md) - How to test and version prompts
- [Roadmap](./ROADMAP.md) - Planned changes for Digital Twin mode
