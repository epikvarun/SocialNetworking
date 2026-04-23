from django.contrib import admin
from .models import ProfileSubmission, ProfileAnalysis, ProfileMatch


@admin.register(ProfileSubmission)
class ProfileSubmissionAdmin(admin.ModelAdmin):
    list_display = ('email', 'instagram_url', 'status', 'submitted_at')
    list_filter = ('status', 'submitted_at')
    search_fields = ('email', 'instagram_url')
    readonly_fields = ('id', 'submitted_at')


@admin.register(ProfileAnalysis)
class ProfileAnalysisAdmin(admin.ModelAdmin):
    list_display = ('instagram_username', 'followers', 'post_count', 'analyzed_at')
    search_fields = ('instagram_username',)
    readonly_fields = ('analyzed_at',)


@admin.register(ProfileMatch)
class ProfileMatchAdmin(admin.ModelAdmin):
    list_display = ('submission', 'matched_instagram_url', 'similarity_score', 'emailed_at')
    list_filter = ('emailed_at',)
    readonly_fields = ('created_at',)
