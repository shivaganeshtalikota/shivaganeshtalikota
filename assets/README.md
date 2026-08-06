# Profile assets

Generated SVGs for the profile README. **Don't edit these by hand** — they are
overwritten on every run of the generator.

| File | Replaces the third-party widget |
|---|---|
| `header.svg` | `capsule-render.vercel.app` |
| `typing.svg` | `readme-typing-svg.demolab.com` |
| `stats.svg` | `github-readme-stats.vercel.app` |
| `languages.svg` | `github-readme-stats.vercel.app/api/top-langs` |
| `activity.svg` | `github-readme-activity-graph.vercel.app` |
| `footer.svg` | `capsule-render.vercel.app` |

## Why these are committed instead of hot-linked

The popular profile-README widgets are all shared free Vercel/Heroku instances.
Observed on this profile:

- `github-readme-stats.vercel.app` → **HTTP 503** (rate limited)
- `github-profile-trophy.vercel.app` → **HTTP 402** (billing lapsed)
- `github-readme-streak-stats.herokuapp.com` → deprecated host
- a community mirror → **HTTP 200 with `Content-Length: 0`**, an empty body that
  renders as a broken image

The last one is the nastiest, because a status-code check passes. And GitHub's
camo image proxy caches a failed fetch, so a broken image stays broken for
viewers long after the upstream recovers.

Serving them from the repo removes the failure mode entirely.

## Regenerating

```bash
python scripts/generate_profile_assets.py      # stdlib only, no pip install
```

Runs unauthenticated against the public API. Set `GITHUB_TOKEN` for the higher
rate limit. `.github/workflows/refresh-profile-assets.yml` runs it daily and
commits any change.
