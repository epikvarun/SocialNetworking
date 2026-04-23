import re
from datetime import timedelta

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import ProfileSubmission
from .tasks import analyze_and_match

_INSTAGRAM_RE = re.compile(
    r'^https?://(www\.)?instagram\.com/[A-Za-z0-9_.]{1,30}/?(\?.*)?$'
)


def index(request):
    return render(request, 'analyzer/index.html')


@require_POST
def submit(request):
    instagram_url = request.POST.get('instagram_url', '').strip().rstrip('/')
    email = request.POST.get('email', '').strip().lower()

    errors: dict[str, str] = {}

    if not instagram_url:
        errors['instagram_url'] = 'Please enter your Instagram profile URL.'
    elif not _INSTAGRAM_RE.match(instagram_url):
        errors['instagram_url'] = (
            'Enter a valid public Instagram profile URL '
            '(e.g. https://www.instagram.com/yourname).'
        )

    if not email:
        errors['email'] = 'Please enter your email address.'

    if errors:
        return JsonResponse({'success': False, 'errors': errors}, status=400)

    # One submission per email per 24 hours
    cutoff = timezone.now() - timedelta(hours=24)
    duplicate = (
        ProfileSubmission.objects.filter(email=email, submitted_at__gte=cutoff)
        .exclude(status=ProfileSubmission.STATUS_FAILED)
        .first()
    )
    if duplicate:
        return JsonResponse(
            {
                'success': False,
                'errors': {
                    'email': (
                        "You've already submitted today. "
                        "Come back tomorrow for your next look-alike!"
                    )
                },
            },
            status=400,
        )

    submission = ProfileSubmission.objects.create(
        email=email,
        instagram_url=instagram_url,
    )
    analyze_and_match.delay(str(submission.id))

    return JsonResponse({'success': True, 'submission_id': str(submission.id)})


@require_GET
def status(request, submission_id):
    try:
        submission = ProfileSubmission.objects.get(id=submission_id)
        return JsonResponse({'status': submission.status})
    except ProfileSubmission.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
