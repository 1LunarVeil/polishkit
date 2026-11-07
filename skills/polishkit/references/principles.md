# Principles and the brief

## Distinctive means specific

A distinctive design is a set of choices made for one subject. Test it by swapping the product name for another product. If the layout, palette and type still work unchanged, the design is a template.

Start from what the product is for. A children's learning app, a bank and a log viewer need different densities, color roles and motion, even when they share a component library. Do not start from a style you like.

## Decision order

Each step constrains the next, so decide in this order:

1. Subject and job: the one thing the main screen must make easy.
2. Audience and context: device, lighting, expertise, hurry, languages.
3. Density and information model: how much is visible at once, and how often it changes.
4. Color roles, then type, then shape (radius, borders, elevation).
5. Motion, then details and copy.

Motion and details come last because they should be rare. Density decides most of the layout, so settle it before debating typefaces.

## The five dimensions

- Typography: one family, or a display and text pair. Say what the type says about the product.
- Color: the dominant neutral, one accent, the semantic set, and the theme or themes.
- Layout: reading order, grid, density, and at most one grid-breaking element.
- Motion: the single moment, if there is one, and the list of things that never animate.
- Details: radius scale, elevation levels, icon family, and imagery or texture if any.

## Brief template

Copy this into the reply, or into `DESIGN.md` if the project keeps one. Leave nothing blank; write "unknown, assumed X" instead.

```
Subject:     what the product is, in one sentence
Audience:    who uses it, on what device, under what conditions
Job:         the one thing the main screen must make easy
Density:     compact, comfortable or spacious, and why
Languages:   zh-CN, en-US, RTL? (affects label width, fonts, line length)
Direction:   name, plus one sentence (references/directions.md)
Typography:  families (self-hosted or system), scale ratio, base size
Color:       dominant neutral, accent, semantic set, themes
Layout:      grid, reading order, the one grid-breaking element or none
Motion:      the one moment, or none; never animate: ...
Details:     radius scale, elevation levels, icon set, imagery
Refusals:    three things this must not look like
Constraints: CSP, offline, token contract, accessibility level, performance
```

## Refusals

Name three things the design must not look like, chosen from `anti-slop.md`. For a local model launcher, that could be: not a marketing landing page, not purple gradients, not a grid of equal tiles. Refusals make the choices checkable, because a reviewer can see whether each one was honoured.

## Reference material

If the user supplies screenshots or a URL, take the direction from it: palette, type character, density and shape. Say what you took. Do not copy a brand's logo, illustrations or a proprietary typeface. Check the license of any font you bundle.

## When the user has no taste yet

Offer two directions from `directions.md`, each with a short token block and its trade-off. Say which one you would ship and why, then proceed with it unless the user chooses otherwise. Options shown as tokens are easier to judge than adjectives: "warm editorial, paper #F7F4EE, serif headings" says more than "warm and elegant".

## Record the decisions

Keep a short decision log in the reply, or in the project brief: one line per choice with its reason. A reviewer can then challenge a reason rather than a mood.
