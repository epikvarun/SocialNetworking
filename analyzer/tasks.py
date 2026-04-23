import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def analyze_and_match(self, submission_id: str):
    """
    Main pipeline: scrape Instagram profile → build feature vector →
    find best match → send email → update submission status.
    Runs within the promised 9-minute window (typically much faster).
    """
    from analyzer.models import ProfileSubmission, ProfileAnalysis, ProfileMatch
    from analyzer.instagram import analyze_profile
    from analyzer.matcher import build_feature_vector, find_best_match, get_match_reasons
    from analyzer.emails import send_match_email, send_waiting_email

    try:
        submission = ProfileSubmission.objects.get(id=submission_id)
    except ProfileSubmission.DoesNotExist:
        logger.error("Submission %s not found", submission_id)
        return

    submission.status = ProfileSubmission.STATUS_ANALYZING
    submission.save(update_fields=['status'])

    # --- 1. Scrape and analyse ---
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

    # --- 2. Find best match from existing profiles ---
    best_analysis, score = find_best_match(str(submission_id), feature_vector)

    if best_analysis:
        reasons = get_match_reasons(
            {
                'hashtag_categories': profile_analysis.hashtag_categories,
                'locations': profile_analysis.locations,
                'top_hashtags': profile_analysis.top_hashtags,
            },
            {
                'hashtag_categories': best_analysis.hashtag_categories,
                'locations': best_analysis.locations,
                'top_hashtags': best_analysis.top_hashtags,
            },
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
        # No suitable match yet — email user and wait for future profiles
        send_waiting_email(submission)
        submission.status = ProfileSubmission.STATUS_WAITING
        # When the next profile comes in, re-check all waiting submissions
        check_waiting_submissions.apply_async(args=[str(submission_id)], countdown=5)

    submission.save(update_fields=['status'])


@shared_task
def check_waiting_submissions(new_submission_id: str):
    """
    After a new profile is analysed, try to match it against every
    submission that is still waiting for a look-alike.
    """
    from analyzer.models import ProfileSubmission, ProfileAnalysis, ProfileMatch
    from analyzer.matcher import cosine_similarity, get_match_reasons, MIN_SIMILARITY
    from analyzer.emails import send_match_email

    try:
        new_analysis = ProfileAnalysis.objects.get(submission_id=new_submission_id)
    except ProfileAnalysis.DoesNotExist:
        return

    waiting_submissions = ProfileSubmission.objects.filter(
        status=ProfileSubmission.STATUS_WAITING
    ).exclude(id=new_submission_id)

    for waiting_sub in waiting_submissions:
        try:
            waiting_analysis = waiting_sub.analysis
        except ProfileAnalysis.DoesNotExist:
            continue

        already_matched = ProfileMatch.objects.filter(
            submission=waiting_sub,
            matched_with_id=new_submission_id,
        ).exists()
        if already_matched:
            continue

        score = cosine_similarity(waiting_analysis.feature_vector, new_analysis.feature_vector)
        if score < MIN_SIMILARITY:
            continue

        reasons = get_match_reasons(
            {
                'hashtag_categories': waiting_analysis.hashtag_categories,
                'locations': waiting_analysis.locations,
                'top_hashtags': waiting_analysis.top_hashtags,
            },
            {
                'hashtag_categories': new_analysis.hashtag_categories,
                'locations': new_analysis.locations,
                'top_hashtags': new_analysis.top_hashtags,
            },
        )

        match = ProfileMatch.objects.create(
            submission=waiting_sub,
            matched_with=new_analysis.submission,
            matched_instagram_url=new_analysis.submission.instagram_url,
            similarity_score=score,
            match_reasons=reasons,
            emailed_at=timezone.now(),
        )

        send_match_email(waiting_sub, match)
        waiting_sub.status = ProfileSubmission.STATUS_MATCHED
        waiting_sub.save(update_fields=['status'])
