import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_match_email(submission, match) -> bool:
    try:
        analysis = submission.analysis
    except Exception:
        analysis = None

    context = {
        'email': submission.email,
        'instagram_username': getattr(analysis, 'instagram_username', ''),
        'matched_instagram_url': match.matched_instagram_url,
        'matched_linkedin_url': match.matched_linkedin_url,
        'match_reasons': match.match_reasons,
        'similarity_score': int(match.similarity_score * 100),
    }

    try:
        html_message = render_to_string('emails/match_found.html', context)
        plain_message = strip_tags(html_message)
        send_mail(
            subject="We found your look-alike! ✨",
            message=plain_message,
            from_email=None,
            recipient_list=[submission.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.error("Failed to send match email to %s: %s", submission.email, exc)
        return False


def send_waiting_email(submission) -> bool:
    try:
        analysis = submission.analysis
    except Exception:
        analysis = None

    context = {
        'email': submission.email,
        'instagram_username': getattr(analysis, 'instagram_username', ''),
    }

    try:
        html_message = render_to_string('emails/no_match_yet.html', context)
        plain_message = strip_tags(html_message)
        send_mail(
            subject="We're searching for your look-alike…",
            message=plain_message,
            from_email=None,
            recipient_list=[submission.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.error("Failed to send waiting email to %s: %s", submission.email, exc)
        return False
