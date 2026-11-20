# Design style preference (animated posts / GIFs)

The user's stated preferences for graphics and GIFs (brand `main`). Designers should read this along with brand.md.

## Identity: Playful Neo-Brutalist Bento Motion
- Warm cream background #F8F4E9 (ivory #FFFDF6) with a faint grid #E8E1D5.
- Ink #171717 / #242424. Pastel accents: lavender #C9B8F5, peach #FFBFA5, butter #F9DE83, mint #B9E5C9,
  baby blue #B8D9F4, coral #F49B91. Use the pastels for cards, highlights and illustrations, and dark ink for text.
- Crisp 2px black borders, 12–22px radius, solid offset shadows (about 6px) plus a soft drop shadow, slight card rotations.
- Space Grotesk 700 for headlines and numbers, Inter 500–800 for body. Small uppercase pill labels.
- Decorations: 4-point stars, a cute blob/face character, floating dots.
- All copy goes in one central CONTENT config in the generator.

## Pick the layout from the content (never reuse one template)
- Tips → numbered stepped cards. Stats → dashboard with charts and counters.
- AI workflows → connected nodes, flow diagrams, floating UI mockups.
- Comparisons → split screen. Checklists → checklist cards. Features → floating product UI.

## Motion
- 6–8 s seamless loop at 24–30 fps, 1080x1350. The GIF must be under 5 MB.
- Frame 0 must be the complete, readable layout because it is used as the thumbnail. Text never fades out.
- The user wants MORE DYNAMIC motion than "cards gently lift" (feedback 2026-11-19). Prefer:
  - bigger, springier movement: cards sliding or popping in with overshoot, whip-pans, elements swapping
  - kinetic type accents: a highlighted word gets stamped, scaled or underlined, with the text staying readable
  - counters, charts and progress that clearly move
  - tokens or arrows racing along connectors
  - a moving character
  - a few strong beats per loop rather than many tiny ones
- GIF size tips: round translate values to whole pixels and don't float every card at once. Sub-pixel motion on
  large areas makes the GIF too big.

## Reference creators (pending)
The user pointed to LinkedIn GIF posts by linkedin.com/in/meenalsinghh and linkedin.com/in/meghanify as the target
"dynamic" feel. Those pages need a LinkedIn login and could not be viewed by the agent, so their style is NOT analysed
yet. Ask the user for screenshots or downloaded GIFs of 3–5 of their posts, then add concrete notes here: layout
patterns, motion beats, pacing, and typography.

## Reference 1 (2026-11-19): "The Enterprise AI Operating Model" GIF, a clean editorial style the user loves
Only frame 0 was shared (a still screenshot), so the motion is not analysed yet. What it shows:
- Landscape 1280x~850. Almost-white canvas with a very faint lavender/blue edge glow (vignette) and a hairline grid.
- Title in a large white pill with a soft blue shadow, at the top centre: black bold grotesk "The Enterprise AI" plus
  an accent pill in light blue (#E8EEFF-ish) holding blue (#3B5BFD-ish) *italic condensed serif* "Operating Model".
- Centre stage: one large white circle with a hairline lavender border, and 2–3 fainter concentric rings behind it.
  The diagram content builds inside or around it (frame 0 is empty, so content animates in).
- Footer bar in white with a soft top glow: round avatar, name in bold, a one-line tagline in grey, brand logo at
  the right.
- Feel: lots of whitespace, hairlines instead of thick borders, a single blue accent, calm and premium. This is NOT
  neo-brutalist. Use it as a second house style ("Clean Editorial") for frameworks, operating models and concepts.
- Note: this reference starts empty and builds up. For our posts, keep frame 0 as a complete layout (the thumbnail
  rule above) OR make the final built-up frame the thumbnail.
