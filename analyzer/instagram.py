import re
import logging
from itertools import islice

logger = logging.getLogger(__name__)

# Keywords per interest category used to score hashtags and captions
INTEREST_KEYWORDS: dict[str, list[str]] = {
    'travel': [
        'travel', 'wanderlust', 'explore', 'adventure', 'backpacking', 'trip',
        'vacation', 'journey', 'tourist', 'abroad', 'nomad', 'globetrotter',
        'passport', 'jetset', 'roamtheplanet', 'instatravel', 'worldtravel',
    ],
    'music': [
        'music', 'jazz', 'hiphop', 'hip_hop', 'indie', 'rock', 'rnb', 'edm',
        'rap', 'pop', 'classical', 'concert', 'festival', 'playlist', 'song',
        'band', 'vinyl', 'livemusic', 'musician', 'producer', 'dj', 'beats',
    ],
    'film': [
        'film', 'cinema', 'movie', 'director', 'screenplay', 'actor', 'actress',
        'netflix', 'hollywood', 'cinephile', 'movienight', 'filmphotography',
        'cinematography', 'screenwriting', 'filmmaking',
    ],
    'food': [
        'food', 'foodie', 'cooking', 'recipe', 'restaurant', 'chef', 'cuisine',
        'gastronomy', 'homecooking', 'brunch', 'dinner', 'instafood',
        'foodphotography', 'baking', 'coffee', 'vegan', 'healthyfood',
    ],
    'art': [
        'art', 'painting', 'design', 'creative', 'illustration', 'artist',
        'artwork', 'gallery', 'exhibition', 'sculpture', 'streetart',
        'contemporaryart', 'digitalart', 'sketch', 'drawing',
    ],
    'sports': [
        'sports', 'fitness', 'gym', 'running', 'yoga', 'football', 'basketball',
        'tennis', 'soccer', 'cycling', 'marathon', 'crossfit', 'workout',
        'athlete', 'training', 'weightlifting',
    ],
    'tech': [
        'tech', 'coding', 'programming', 'startup', 'developer', 'software',
        'ai', 'innovation', 'engineering', 'entrepreneur', 'saas', 'webdev',
        'machinelearning', 'python', 'javascript',
    ],
    'nature': [
        'nature', 'hiking', 'mountains', 'ocean', 'forest', 'wildlife', 'camping',
        'outdoors', 'landscape', 'sunset', 'earthpix', 'natgeo', 'wilderness',
        'trekking', 'climbing',
    ],
}

_HASHTAG_RE = re.compile(r'#(\w+)')
_USERNAME_RE = re.compile(r'instagram\.com/([A-Za-z0-9_.]+)(?:/|\?|$)')
_RESERVED = frozenset({'p', 'reel', 'reels', 'stories', 'explore', 'accounts', 'tv'})


def extract_username(instagram_url: str) -> str | None:
    match = _USERNAME_RE.search(instagram_url)
    if match:
        username = match.group(1)
        if username not in _RESERVED:
            return username
    return None


def categorize_hashtags(hashtags: list[str]) -> dict[str, int]:
    categories = {cat: 0 for cat in INTEREST_KEYWORDS}
    for tag in hashtags:
        tag_lower = tag.lower()
        for category, keywords in INTEREST_KEYWORDS.items():
            if any(kw in tag_lower for kw in keywords):
                categories[category] += 1
                break  # count each tag in at most one category
    return categories


def analyze_profile(instagram_url: str) -> dict | None:
    username = extract_username(instagram_url)
    if not username:
        logger.error("Could not extract username from %s", instagram_url)
        return None

    try:
        import instaloader
        loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
        )
        profile = instaloader.Profile.from_username(loader.context, username)

        all_hashtags: list[str] = []
        locations: list[str] = []

        for post in islice(profile.get_posts(), 50):
            if post.caption:
                all_hashtags.extend(_HASHTAG_RE.findall(post.caption))
            if post.location and post.location.name:
                loc = post.location.name
                if loc not in locations:
                    locations.append(loc)

        hashtag_categories = categorize_hashtags(all_hashtags)

        counts: dict[str, int] = {}
        for tag in all_hashtags:
            counts[tag.lower()] = counts.get(tag.lower(), 0) + 1
        top_hashtags = sorted(counts, key=counts.get, reverse=True)[:20]  # type: ignore[arg-type]

        return {
            'username': username,
            'followers': profile.followers,
            'following': profile.followees,
            'post_count': profile.mediacount,
            'bio': profile.biography or '',
            'hashtag_categories': hashtag_categories,
            'top_hashtags': top_hashtags,
            'locations': locations[:20],
        }

    except Exception as exc:
        # Graceful degradation: return minimal data so we can still create a record
        logger.warning("Instagram scrape failed for %s: %s", username, exc)
        return {
            'username': username,
            'followers': 0,
            'following': 0,
            'post_count': 0,
            'bio': '',
            'hashtag_categories': {cat: 0 for cat in INTEREST_KEYWORDS},
            'top_hashtags': [],
            'locations': [],
            'scrape_error': str(exc),
        }
