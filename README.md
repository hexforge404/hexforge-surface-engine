# hexforge-glyphengine


hexforge-glyphengine
 (HGE) is a texture-first surface and enclosure generation engine for fabrication workflows.

# HexForge GlyphEngine

**HexForge GlyphEngine** is a texture-first surface and enclosure generation
engine for fabrication workflows.


GlyphEngine implements the **Surface v1 API**, which focuses on generating
repeatable, displacement-ready surface detail and parametric enclosures for
3D printing, CNC, and hybrid CAD workflows.



## Primary Outputs

- Displacement-ready texture assets  
  (heightmaps, with optional normals and masks)
- Parametric enclosure geometry  
  (STL for printing, plus Blender / CAD-friendly handoff formats)
- Preview renders suitable for:
  - Product listings
  - Documentation
  - Social and marketing assets


## Stack Integration

GlyphEngine is designed as a **headless engine** within the HexForge stack:

- **Frontend UI**
  - Job creation
  - Preview display
  - Asset downloads
- **Backend API Gateway**
  - Authentication
  - Persistence
  - Routing
- **HexForge Assistant**
  - Job orchestration
  - Parameter validation
  - Workflow helpers
  - Multi-engine coordination (future)

## Core Focus (Surface v1)

- Diffusion-based texture generation → heightmap output
- UV-displacement workflow for applying textures to enclosure surfaces
  (non-destructive, CAD-friendly)
- Parametric enclosure generation (CadQuery-first)
- Stable filesystem layout and public URLs for all generated assets


## Explicit Non-Goals (Surface v1)

The following are intentionally **out of scope** for v1:

- Full AI text-to-3D mesh generation
- G-code generation or slicer replacement
- Complex CAD editing UI
- Marketplace or community features

These may be addressed by **future engines**, not GlyphEngine itself.


## High-Level Pipeline

1. User defines enclosure parameters and style prompt
2. Texture generator creates base pattern image(s)
3. Texture processor produces heightmap
   (and optional normals / masks)
4. Enclosure generator produces:
   - Base geometry
   - Mapping references
5. Outputs and previews are written to canonical public asset folders
6. UI displays previews and exposes downloadable assets


## Naming Clarification

- **Repository / Service name:** HexForge GlyphEngine
- **API + asset namespace:** Surface v1 (`/api/surface`, `/assets/surface`)
- **Reason:**  
  GlyphEngine is the *engine family*.  
  Surface v1 is the *first public contract*.

This preserves backward compatibility while allowing future engines
(e.g. Relief, Pattern, Lattice, Panel) to coexist cleanly.
