import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CATEGORIES = ['travel', 'music', 'film', 'food', 'art', 'sports', 'tech', 'nature']
MIN_SIMILARITY = 0.25  # minimum cosine similarity to consider a match valid


def build_feature_vector(analysis_data: dict) -> list[float]:
    """Convert a profile analysis dict into a normalized float vector."""
    cats = analysis_data.get('hashtag_categories', {})
    total = sum(cats.values()) or 1

    # Category proportions (8 dims)
    cat_features = [cats.get(cat, 0) / total for cat in CATEGORIES]

    # Follower scale: log10(n+1) normalised to ~[0,1] assuming max ~10M followers
    followers = max(analysis_data.get('followers', 0), 0)
    follower_feature = math.log10(followers + 1) / 7.0

    # Location diversity: capped at 20 unique locations, normalised
    location_feature = min(len(analysis_data.get('locations', [])), 20) / 20.0

    return cat_features + [follower_feature, location_feature]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def find_best_match(
    submission_id: str, feature_vector: list[float]
) -> tuple[Optional['ProfileAnalysis'], float]:  # type: ignore[name-defined]
    from analyzer.models import ProfileAnalysis, ProfileMatch

    already_matched_ids = ProfileMatch.objects.filter(
        submission_id=submission_id
    ).values_list('matched_with_id', flat=True)

    candidates = (
        ProfileAnalysis.objects.exclude(submission_id=submission_id)
        .exclude(submission_id__in=already_matched_ids)
        .select_related('submission')
    )

    best_analysis = None
    best_score = 0.0

    for candidate in candidates:
        if not candidate.feature_vector:
            continue
        score = cosine_similarity(feature_vector, candidate.feature_vector)
        if score > best_score:
            best_score = score
            best_analysis = candidate

    if best_score < MIN_SIMILARITY:
        return None, best_score

    return best_analysis, best_score


def get_match_reasons(analysis_a: dict, analysis_b: dict) -> list[str]:
    reasons: list[str] = []

    cats_a = analysis_a.get('hashtag_categories', {})
    cats_b = analysis_b.get('hashtag_categories', {})
    total_a = sum(cats_a.values()) or 1
    total_b = sum(cats_b.values()) or 1

    shared_cats = [
        cat for cat in CATEGORIES
        if cats_a.get(cat, 0) / total_a > 0.08 and cats_b.get(cat, 0) / total_b > 0.08
    ]
    if shared_cats:
        reasons.append(f"Shared passion for {', '.join(shared_cats)}")

    locs_a = set(analysis_a.get('locations', []))
    locs_b = set(analysis_b.get('locations', []))
    shared_locs = locs_a & locs_b
    if shared_locs:
        sample = list(shared_locs)[:3]
        reasons.append(f"Both have been to {', '.join(sample)}")

    tags_a = set(t.lower() for t in analysis_a.get('top_hashtags', [])[:15])
    tags_b = set(t.lower() for t in analysis_b.get('top_hashtags', [])[:15])
    shared_tags = tags_a & tags_b
    if shared_tags:
        sample = list(shared_tags)[:3]
        reasons.append(f"Common hashtags: #{'  #'.join(sample)}")

    return reasons or ["Very similar overall vibe and creative interests"]
