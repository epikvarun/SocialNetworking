import logging
import threading

logger = logging.getLogger(__name__)


def _run_in_thread(submission_id: str):
    """Runs the full pipeline in a daemon thread — no Celery/Redis required."""
    import django
    django.setup()  # ensure Django is initialised for this thread

    from analyzer.models import ProfileSubmission, ProfileAnalysis, ProfileMatch
    from analyzer.instagram import analyze_profile
    from analyzer.matcher import build_feature_vector, find_best_match, get_match_reasons
    from analyzer.emails import send_match_email, send_waiting_email
    from django.utils import timezone

    try:
        submission = ProfileSubmission.objects.get(id=submission_id)
    except ProfileSubmission.DoesNotExist:
        logger.error("Submission %s not found", submission_id)
        return

    submission.status = ProfileSubmission.STATUS_ANALYZING
    submission.save(update_fields=['status'])

    analysis_data = analyze_profile(submission.instagram_url)
    if not analysis_data:
        submission.status = ProfileSubmission.STATUS_FAILED
        submission.save(update_fields=['status'])
        return

    feature_vector = build_feature_vector(analysis_data)

    profile_analysis, _ = ProfileAnalysis.objects.get_or_create(
        submission=submission,
        defaults={
            'instagram_username': analysis_data['username'],
            'followers': analysis_data['followers'],
            'following': analysis_data['following'],
            'post_count': analysis_data['post_count'],
            'bio': analysis_data['bio'],
            'hashtag_categories': analysis_data['hashtag_categories'],
            'top_hashtags': analysis_data['top_hashtags'],
            'locations': analysis_data['locations'],
            'feature_vector': feature_vector,
        },
    )

    best_analysis, score = find_best_match(str(submission_id), feature_vector)

    if best_analysis:
        reasons = get_match_reasons(
            {'hashtag_categories': profile_analysis.hashtag_categories,
             'locations': profile_analysis.locations,
             'top_hashtags': profile_analysis.top_hashtags},
            {'hashtag_categories': best_analysis.hashtag_categories,
             'locations': best_analysis.locations,
             'top_hashtags': best_analysis.top_hashtags},
        )
        match = ProfileMatch.objects.create(
            submission=submission,
            matched_with=best_analysis.submission,
            matched_instagram_url=best_analysis.submission.instagram_url,
            similarity_score=score,
            match_reasons=reasons,
            emailed_at=timezone.now(),
        )
        send_match_email(submission, match)
        submission.status = ProfileSubmission.STATUS_MATCHED
    else:
        send_waiting_email(submission)
        submission.status = ProfileSubmission.STATUS_WAITING
        # Retry matching for any previously waiting submissions
        _retry_waiting(submission_id, profile_analysis)

    submission.save(update_fields=['status'])


def _retry_waiting(new_id: str, new_analysis):
    from analyzer.models import ProfileSubmission, ProfileAnalysis, ProfileMatch
    from analyzer.matcher import cosine_similarity, get_match_reasons, MIN_SIMILARITY
    from analyzer.emails import send_match_email
    from django.utils import timezone

    for waiting in ProfileSubmission.objects.filter(status=ProfileSubmission.STATUS_WAITING).exclude(id=new_id):
        try:
            wa = waiting.analysis
        except ProfileAnalysis.DoesNotExist:
            continue
        if ProfileMatch.objects.filter(submission=waiting, matched_with_id=new_id).exists():
            continue
        score = cosine_similarity(wa.feature_vector, new_analysis.feature_vector)
        if score < MIN_SIMILARITY:
            continue
        reasons = get_match_reasons(
            {'hashtag_categories': wa.hashtag_categories, 'locations': wa.locations, 'top_hashtags': wa.top_hashtags},
            {'hashtag_categories': new_analysis.hashtag_categories, 'locations': new_analysis.locations, 'top_hashtags': new_analysis.top_hashtags},
        )
        from django.utils import timezone
        match = ProfileMatch.objects.create(
            submission=waiting, matched_with=new_analysis.submission,
            matched_instagram_url=new_analysis.submission.instagram_url,
            similarity_score=score, match_reasons=reasons, emailed_at=timezone.now(),
        )
        send_match_email(waiting, match)
        waiting.status = ProfileSubmission.STATUS_MATCHED
        waiting.save(update_fields=['status'])


def analyze_and_match(submission_id: str):
    """Fire-and-forget: starts the pipeline in a background thread."""
    t = threading.Thread(target=_run_in_thread, args=(submission_id,), daemon=True)
    t.start()
