# 04. Design Brief

Mobile first PWA. The visual direction is chosen in phase 6 with the ui-ux-pro-max skill; this brief fixes goals, constraints and required screens so that the choice stays testable.

## 1. Goals
1. Ask by typing, speaking or attaching a screenshot in two taps.
2. Make trust visible: citations, confidence, refusals, and what was searched.
3. Feel fast on a phone and on a slow network.
4. Give the admin a clear, honest quality dashboard.

## 2. Principles
- Answers first, chrome second. One primary action per screen.
- Never hide uncertainty. A refusal is a designed state, not an error.
- Every number on screen comes from a measured source with its run date.
- Plain, honest copy. No hyphens in user facing text. No marketing claims.

## 3. Platforms and constraints
Phone widths 360 to 430 px first, then tablet and desktop. Installable PWA (manifest, icons, offline shell). A build step only if it earns its place. Touch targets at least 44 px. Respect reduced motion and color scheme preferences.

## 4. Screens
| Screen | Key elements |
|---|---|
| Login / guest | email and password, continue as guest, honest note that demo accounts are for testing |
| Chat | message list, composer with text, mic (hold or tap), attach image, send; streaming answer; suggested questions |
| Answer card | answer text, numbered citations, copy code button, confidence cue, feedback thumbs, why this answer (steps taken) |
| Source drawer | chunk text, page title, link to the original doc, score |
| Refusal state | what was searched, why it was not enough, nearest pages |
| History | past chats, search, delete |
| Memory manager | list by type, edit, delete, toggle memory off |
| Settings | theme, speak replies, voice, data and privacy note |
| Admin: Users | list, role change, disable, audit log |
| Admin: Evals | latest run status, trend lines per metric, per question type table, regressions, run now, schedule status |
| Admin: System | latency p50 and p95, tokens, cost, cache hit rate, fallback rate, provider status |

## 5. States to design
Loading and streaming, empty chat, offline, rate limited, provider failover notice, mic recording, transcript confirm, image preview, long code answers, error, session expired, cold start.

## 6. Visual direction (decided in phase 6)
Developer friendly, calm, high contrast, code first typography (monospace for code, readable sans for text). Dark and light themes from tokens. Dashboard charts follow the dataviz skill (accessible colours, no decoration). Two or three candidate directions are shown as small mockups before one is chosen.

## 7. Accessibility
WCAG 2.2 AA: contrast, focus order, labels, a live region for streaming answers, a transcript for any audio, a keyboard path for everything. Voice is never the only way.

## 8. Content rules
Short sentences. State limits plainly: free tier, may be slow, answers can be wrong, check the source. No invented stats.

## 9. Acceptance checks
Lighthouse mobile run recorded in the README with actual scores; manual pass on a real phone; axe or equivalent run; each screen above exists or is explicitly marked not built.
