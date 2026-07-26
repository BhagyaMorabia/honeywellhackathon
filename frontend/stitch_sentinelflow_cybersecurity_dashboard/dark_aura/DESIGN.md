---
name: Dark Aura
colors:
  surface: '#0e1514'
  surface-dim: '#0e1514'
  surface-bright: '#333b3a'
  surface-container-lowest: '#090f0f'
  surface-container-low: '#161d1c'
  surface-container: '#1a2120'
  surface-container-high: '#242b2a'
  surface-container-highest: '#2f3635'
  on-surface: '#dde4e2'
  on-surface-variant: '#bacac7'
  inverse-surface: '#dde4e2'
  inverse-on-surface: '#2b3231'
  outline: '#859491'
  outline-variant: '#3c4948'
  surface-tint: '#3cdcd1'
  primary: '#ffffff'
  on-primary: '#003734'
  primary-container: '#62f9ee'
  on-primary-container: '#00716b'
  inverse-primary: '#006a64'
  secondary: '#bec7d6'
  on-secondary: '#28313c'
  secondary-container: '#3e4753'
  on-secondary-container: '#adb6c4'
  tertiary: '#ffffff'
  on-tertiary: '#2f3035'
  tertiary-container: '#e3e2e8'
  on-tertiary-container: '#646469'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#62f9ee'
  primary-fixed-dim: '#3cdcd1'
  on-primary-fixed: '#00201e'
  on-primary-fixed-variant: '#00504b'
  secondary-fixed: '#dae3f2'
  secondary-fixed-dim: '#bec7d6'
  on-secondary-fixed: '#131c27'
  on-secondary-fixed-variant: '#3e4753'
  tertiary-fixed: '#e3e2e8'
  tertiary-fixed-dim: '#c7c6cb'
  on-tertiary-fixed: '#1a1b20'
  on-tertiary-fixed-variant: '#46464b'
  background: '#0e1514'
  on-background: '#dde4e2'
  surface-variant: '#2f3635'
typography:
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-xs:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin: 24px
  container-max: 1440px
---

## Brand & Style
The design system is a high-performance, tactical framework engineered for "SentinelFlow." It evokes a sense of "military-grade" precision, reliability, and technical dominance. The aesthetic is rooted in **Modern Tactical Minimalism** with a heavy influence from **Glassmorphism**, optimized for low-light environments and expert-level situational awareness.

The visual narrative focuses on density and clarity. It avoids decorative "fluff" in favor of utility and immediate data recognition. Every element serves a functional purpose, utilizing thin structural lines and controlled luminescent accents to guide the user's eye through complex data environments without causing cognitive fatigue.

## Colors
The palette is built on a foundation of deep, non-pure blacks to maintain depth and reduce eye strain.

- **Surface Layering:** The primary background uses `#0B0C10` (Obsidian), providing a "void-like" canvas. UI containers and panels use `#1F2833` (Slate) with transparency to support backdrop blurring.
- **Accents & Semantics:** 
    - **Primary Cyan (#66FCF1):** Used for normal operations, connectivity, and primary calls to action. It should feel "energized."
    - **Critical Crimson (#FF003C):** Reserved for brute-force attacks, system failures, or immediate threats.
    - **Alert Amber (#FF8A00):** Used for configuration drifts, anomalies, and high-priority warnings.
- **Contrast:** Typography primarily uses `#C5C6C7` for high legibility against dark backgrounds without the harshness of pure white.

## Typography
Typography is split between a sleek, geometric sans-serif for interface navigation and a technical monospaced font for data output.

- **Headings (Geist):** Tight tracking and high-weight weights convey authority.
- **Body (Inter):** Highly legible at small sizes, used for descriptions and documentation.
- **Data (JetBrains Mono):** The workhorse of the system. **Tabular figures (tabular-nums)** are mandatory for all numerical data to ensure vertical alignment in tables and logs.
- **Hierarchy:** Use all-caps labels for metadata and technical specs to reinforce the tactical aesthetic.

## Layout & Spacing
The layout employs a **high-density fluid grid** based on a 4px baseline. 

- **Density:** Information density should be high. Minimize "dead" whitespace; instead, use 1px borders to separate modules.
- **Grid:** A 12-column grid is used for desktop, collapsing to 4 columns on mobile. 
- **Alignment:** All technical data must be left-aligned in columns to allow for rapid scanning of log entries. 
- **Sidebars:** Persistent left-hand navigation for global controls and a right-hand "Inspector" panel for specific node details.

## Elevation & Depth
Depth is created through transparency and blur rather than shadows. 

- **Glassmorphism:** Panels use a 60-80% opacity fill of the Slate color (`#1F2833`) with a `backdrop-filter: blur(12px)`.
- **Borders:** Every container must have a 1px solid border. The border color should be a slightly lighter version of the panel color (approx. 15-20% opacity white) to catch the light.
- **Glow Effects:** Active states (hovered buttons, selected nodes) should utilize a subtle outer glow (box-shadow) using the element's accent color (Cyan, Crimson, or Amber) with a 10px-15px blur radius at low opacity (0.3).

## Shapes
The shape language is rigid and sharp.

- **Corners:** Use a consistent 4px radius (`rounded-sm`) for most UI components (buttons, panels, inputs). This provides a "machined" look that is cleaner than raw 0px corners but far more professional than "bubbly" rounded UI.
- **Indicators:** Status indicators should be square or diamond-shaped rather than circular to maintain the geometric, tactical feel.

## Components
- **Buttons:** Ghost-style by default with 1px Cyan borders. Solid fills are reserved for primary actions. Text is always uppercase JetBrains Mono.
- **Inputs:** Dark backgrounds (`#0B0C10`) with a 1px Slate border. On focus, the border transitions to Cyan with a subtle 4px glow.
- **Cards/Panels:** Utilize the Glassmorphism specification. Header sections of cards should have a subtle 10% opacity Cyan tint to indicate they are interactive.
- **Chips/Tags:** Small, rectangular labels with monospaced text. Backgrounds are high-opacity versions of the status colors (Crimson/Amber/Cyan) with white or near-white text for maximum contrast.
- **Logs/Lists:** Alternating row highlights (zebra striping) using a 5% opacity white overlay. Hovering over a row should trigger a 1px Cyan left-edge border.
- **Terminal Component:** A specialized monospaced view with a blinking Cyan cursor, used for real-time brute-force monitoring or system logs.