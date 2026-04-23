import uuid
from django.db import models


class ProfileSubmission(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ANALYZING = 'analyzing'
    STATUS_MATCHED = 'matched'
    STATUS_WAITING = 'waiting'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ANALYZING, 'Analyzing'),
        (STATUS_MATCHED, 'Matched'),
        (STATUS_WAITING, 'Waiting for Match'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    instagram_url = models.URLField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.email} → {self.instagram_url}"


class ProfileAnalysis(models.Model):
    submission = models.OneToOneField(
        ProfileSubmission, on_delete=models.CASCADE, related_name='analysis'
    )
    instagram_username = models.CharField(max_length=100)
    followers = models.IntegerField(default=0)
    following = models.IntegerField(default=0)
    post_count = models.IntegerField(default=0)
    bio = models.TextField(blank=True)
    # Category interest counts extracted from hashtags/captions
    hashtag_categories = models.JSONField(default=dict)
    # Top 20 hashtags used
    top_hashtags = models.JSONField(default=list)
    # Unique location names from posts
    locations = models.JSONField(default=list)
    # Normalized feature vector for cosine similarity matching
    feature_vector = models.JSONField(default=list)
    analyzed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"@{self.instagram_username}"


class ProfileMatch(models.Model):
    submission = models.ForeignKey(
        ProfileSubmission, on_delete=models.CASCADE, related_name='matches'
    )
    matched_with = models.ForeignKey(
        ProfileSubmission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_to',
    )
    matched_instagram_url = models.URLField(blank=True)
    matched_linkedin_url = models.URLField(blank=True)
    similarity_score = models.FloatField(default=0.0)
    match_reasons = models.JSONField(default=list)
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Match for {self.submission.email} (score={self.similarity_score:.2f})"
