---
name: Fiscal Clarity
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#3e4947'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#6e7977'
  outline-variant: '#bdc9c6'
  surface-tint: '#006a63'
  primary: '#005c55'
  on-primary: '#ffffff'
  primary-container: '#0f766e'
  on-primary-container: '#a3faef'
  inverse-primary: '#80d5cb'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#7f4025'
  on-tertiary: '#ffffff'
  tertiary-container: '#9c573a'
  on-tertiary-container: '#ffe5db'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#9cf2e8'
  primary-fixed-dim: '#80d5cb'
  on-primary-fixed: '#00201d'
  on-primary-fixed-variant: '#00504a'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#ffdbce'
  tertiary-fixed-dim: '#ffb598'
  on-tertiary-fixed: '#370e00'
  on-tertiary-fixed-variant: '#72361b'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
  text-primary: '#0F172A'
  text-secondary: '#64748B'
  border-subtle: '#E2E8F0'
  compliance-amber: '#D97706'
  surface-white: '#FFFFFF'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.2'
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  container-max-width: 800px
  gutter: 24px
  margin-mobile: 16px
  message-gap: 12px
  section-padding: 40px
---

## Brand & Style
The design system is engineered for a "Mutual Fund FAQ Assistant," prioritizing institutional trust and clarity over decorative flair. The aesthetic is **Minimalist-Modern**, drawing inspiration from high-end editorial layouts and financial SaaS interfaces. 

The brand personality is authoritative yet accessible, using generous white space and a structured hierarchy to make complex financial information digestible. It avoids the "gamified" appearance of consumer trading apps, opting instead for a stable, professional environment that encourages careful reading and considered decision-making.

## Colors
The palette is rooted in a **Deep Teal** primary, chosen for its psychological association with stability and sophisticated growth. 

- **Background Strategy:** The primary canvas uses a soft off-white (`#F8FAFC`) to reduce eye strain, while interactive elements and content containers use pure white (`#FFFFFF`) to create a subtle layered effect.
- **Functional Accents:** The **Compliance Amber** is reserved strictly for legal disclaimers and risk warnings, ensuring these critical pieces of information are noticed without breaking the calm aesthetic.
- **Typography Contrast:** Use Slate-900 for all primary headings and body text to ensure maximum legibility and AAA accessibility.

## Typography
This design system utilizes **Inter** exclusively to maintain a utilitarian, highly legible, and neutral tone. 

The core of the experience is the **Body-MD** and **Body-LG** styles, which feature a generous 1.6 line-height. This "editorial" spacing is intentional, preventing dense financial explanations from feeling overwhelming. Headlines use a slightly tighter letter-spacing and heavier weights to provide clear structural anchors in long-form text. All labels and secondary text should use Slate-500 to maintain a clear information hierarchy.

## Layout & Spacing
The layout follows a **Fixed Center-Column** model. For a chat-based assistant, content is constrained to a maximum width of 800px to ensure optimal line length for reading.

- **Rhythm:** Use a 4px baseline grid. Most spacing increments should be multiples of 8px (16, 24, 32, 48).
- **Chat Flow:** Vertical spacing between message bubbles is 12px, while spacing between distinct "turns" in the conversation is 24px.
- **Sticky Elements:** The header and input bar are anchored to the viewport. The input bar should have a maximum width matching the content container, centered with a subtle blur effect on the background behind it.

## Elevation & Depth
Depth is conveyed through **Tonal Layering** and soft, ambient shadows rather than traditional high-contrast shadows.

- **Level 0 (Background):** Slate-50 surface (`#F8FAFC`).
- **Level 1 (Cards/Bubbles):** White surface (`#FFFFFF`) with a very soft shadow: `0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05)`.
- **Level 2 (Sticky Headers/Inputs):** White surface with a thin bottom border (`#E2E8F0`) and a slightly more pronounced shadow to indicate they sit above the scrolling content.
- **Interaction:** Buttons use a small 2px translation (lift) on hover rather than an increase in shadow spread to maintain the minimal feel.

## Shapes
The shape language is "Soft-Modern." It uses a dual-radius system to distinguish between structural containers and interactive elements:

- **Structural (Cards, Modals):** 12px (`rounded-lg`) for a friendly, approachable frame.
- **Interactive (Buttons, Inputs, Chips):** 8px (`rounded-md`) to provide a more precise, functional appearance.
- **Message Bubbles:** Follow the 12px card radius, but may use a 4px radius on the corner adjacent to the sender to provide directional "tails."

## Components

### Chat Bubbles
- **User Message:** Deep Teal background, White text. Aligned to the right. No border.
- **Assistant Message:** White background, Slate-900 text. Aligned to the left. 1px Slate-200 border.

### Suggestion Chips
- **Style:** Ghost-style chips with 1px Slate-200 border, White background, and Slate-900 text.
- **Interaction:** On hover, the border darkens to Slate-400 and the background shifts to Slate-50.

### Buttons
- **Primary:** Deep Teal background, White text, 8px radius. 
- **Secondary:** Transparent background, Deep Teal text and border.

### Input Bar
- **Container:** Sticky at the bottom, White background, Slate-200 top border.
- **Field:** 8px radius, Slate-50 background, subtle 1px border. Helper text (Slate-500) sits immediately below the input field within the sticky area.

### Disclaimer Banner
- **Style:** Amber-50 background, Amber-700 text. Placed immediately below the sticky header. Uses a small informational icon and **Body-SM** typography.