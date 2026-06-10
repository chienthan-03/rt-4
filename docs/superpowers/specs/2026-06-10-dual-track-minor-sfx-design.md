# Dual-Track Minor SFX — Design Spec (Phase B)

**Date:** 2026-06-10  
**Depends on:** Phase A (Smart Major SFX)  
**Goal:** Thêm Tier 1 Attention SFX (whoosh/pop/click) song song major sounds, theo công thức TikTok `1 Major + 2–5 Minor / 10s`.

## Scope

### In scope
- Tier `attention` trong sound library
- Detect minor cues từ `scene_change` visual events
- Chọn minor sound theo cue type (không LLM)
- Density planner: tối đa 5 minor / 10s, tối thiểu giữ cues tự nhiên
- Merge placements: major ưu tiên khi overlap, minor volume thấp hơn

### Out of scope (moved to niche UI task)
- ~~UI niche selector~~ — implemented separately
- LLM cho minor selection
- Synthetic filler cues khi video ít scene cut

## Architecture

```
visual_events (scene_change)
    → extract_minor_cues (lọc gần major peaks)
    → plan_minor_density (cap 2–5 / 10s window)
    → select_minor_sounds (attention tier, rotate)
    → create_minor_placements (volume × 0.5)
    → merge_placements(major, minor)
```

## Rules

| Rule | Value |
|------|-------|
| Minor source | `scene_change` events |
| Skip near major | ±1200ms từ major peak |
| Min gap giữa minor | 400ms |
| Max minor / 10s | 5 |
| Minor volume | `meme_volume × 0.5` |
| Overlap resolution | Major luôn thắng minor |

## Attention sound map

| Cue type | Aliases |
|----------|---------|
| scene_change | whoosh, woosh, swipe |
| transition | pop, click |

## Success criteria

- [ ] Video 30s có major (Phase A) + minor trên scene cuts
- [ ] ≤ 5 minor mỗi cửa sổ 10s
- [ ] Không overlap minor lên major peak
- [ ] Tests pass
