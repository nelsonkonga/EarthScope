# Pexels image register — Terra Sense

Every photograph shown on the landing page has a row here and a matching entry in
`src/features/landing/photos.ts`. Files are served locally from `public/images/` (no hotlinking).
They are illustrations: none of them is data, a measurement, or imagery analyzed by Terra Sense.

Selection supplied by the project team on 2026-11-15 (Pexels page URL and photographer name).
Files downloaded the same day from `images.pexels.com` (the Pexels CDN for each photo ID),
then resized, cropped where noted, and converted to WebP (quality 68–80).

Terms: used under the Pexels License (free use, modification allowed, attribution not required).
By decision of the project team, no credit or Pexels mention is shown in the interface; this
register keeps the provenance. The license page itself (pexels.com/license) could not be opened from
the build environment, which blocks automated access to www.pexels.com; check it before release.

| Local file | Used in | Pexels title / description | Photographer | Pexels URL | Downloaded | Terms checked | Crops (desktop / mobile) |
|---|---|---|---|---|---|---|---|
| `hero-soil-landscape.webp` (1600×900), `hero-soil-landscape-mobile.webp` (960×720) | Hero, photo plate under the conceptual soil section (`HeroSection`) | Roots in brown soil | Mikhail Nilov | https://www.pexels.com/photo/roots-in-brown-soil-7675949/ | 2026-11-15 | Pexels License (see note) | Desktop: full frame, shown 5:6 with `object-fit: cover`, centered. Mobile: dedicated 4:3 center crop (75% width) |
| `agriculture-field.webp` (1200×800) | Problem section, card 01 Agriculture | Aerial view of expansive green crop field | Jan van der Wolf | https://www.pexels.com/photo/aerial-view-of-expansive-green-crop-field-40950120/ | 2026-11-15 | Pexels License (see note) | 4:3 card crop, position 50% 45% |
| `ecosystem-savanna.webp` (1200×800) | Problem section, card 02 Ecosystems | Trees on savanna | Abdallah Mallya | https://www.pexels.com/photo/trees-on-savanna-16253414/ | 2026-11-15 | Pexels License (see note) | 1:1 card crop on desktop, 4:3 on mobile, position 38% 55% |
| `water-resource.webp` (1200×800) | Problem section, card 03 Water cycle | A woman fetching water from a deep well | Mehmet Turgut Kirkgoz | https://www.pexels.com/photo/a-woman-fetching-water-from-a-deep-well-12068384/ | 2026-11-15 | Pexels License (see note) | 16:10 card crop, position 56% 60% (58% on mobile) |
| `satellite-earth-observation.webp` (1400×788) | Mission section, capability 01 Observe the Earth | Earth view with satellite from space (appears to be a 3D render) | Zelch Csaba | https://www.pexels.com/photo/earth-view-with-satellite-from-space-30596312/ | 2026-11-15 (original PNG) | Pexels License (see note) | File cropped to 62% of the width around the satellite (16:9); shown 16:9, position 72% 55% |
| `trend-analysis.webp` (1400×788) | Mission section, capability 02 Identify trends | A person using a laptop (time-series curve on screen) | Mikhail Nilov | https://www.pexels.com/photo/a-person-using-a-laptop-6930431/ | 2026-11-15 | Pexels License (see note) | File cropped to 16:9 around the laptop (center 50% 45%); shown 16:9 |
| `results-reading.webp` (1400×788) | Mission section, capability 03 Understand the results | A person using laptop (reading a chart) | Artem Podrez | https://www.pexels.com/photo/a-person-using-laptop-8518665/ | 2026-11-15 | Pexels License (see note) | File cropped from portrait to 16:9 around the laptop (center 50% 36%); shown 16:9. Screen shows a generic infographic mock-up with small text |
| `soil-research-fieldwork.webp` (1400×788) | About dialog, header image | Crop farmer preparing soil for planting | Greta Hoffman | https://www.pexels.com/photo/crop-farmer-preparing-soil-for-planting-7728051/ | 2026-11-15 | Pexels License (see note) | File cropped from portrait to 16:9 around the hands; shown 21:9 (16:9 on mobile), position 50% 58% |

Alternatives supplied but not used (not shipped): 31785157 (Tuan Vy), 17765487 (Mark Stebnicki),
32382761 (Charmain Jansen van Rensburg), 30596266 (Zelch Csaba), 10468213 (Vinícius Cezário, purple
trading screen, off palette), 9574338 and 9574343 (Tima Miroshnichenko, clinical lab, blank screens).
