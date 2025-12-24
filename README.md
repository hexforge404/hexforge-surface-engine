# HexForge Surface Engine

HexForge Surface Engine (HSE) is a texture-first surface and enclosure generation engine for fabrication workflows.

Primary outputs:
- Displacement-ready texture assets (heightmaps, optional normals/masks)
- Parametric enclosure geometry (STL for print, plus Blender/CAD-friendly handoff formats)
- Previews suitable for product listings and social posts

HSE is designed to integrate with the HexForge stack:
- Frontend UI (job creation + previews + downloads)
- Backend API gateway (auth, persistence, routing)
- HexForge Assistant (orchestration + parameter validation + workflow helpers)

## Core Focus (v1)
- Diffusion-based texture generation → heightmap output
- UV-displacement workflow for applying textures to enclosure surfaces (non-destructive)
- Parametric enclosure generator (CadQuery-first)
- Stable filesystem + URLs for all generated assets

## Explicit Non-Goals (v1)
- Full AI text-to-3D mesh generation
- Generating G-code / replacing slicers
- Complex CAD editing UI
- Marketplace/community features

## High-Level Pipeline
1) User defines enclosure parameters + style prompt
2) Texture generator creates pattern image(s)
3) Texture processor produces heightmap (and optional normal/masks)
4) Enclosure generator produces base geometry + mapping reference
5) Outputs + previews are written to canonical public asset folders
6) UI displays previews and provides downloads



sudo chown -R devuser:devuser /mnt/hdd-storage/hexforge-surface-engine
