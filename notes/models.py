from django.conf import settings
from django.db import models


class Note(models.Model):
    SOURCE_TYPES = (("image", "Image"), ("pdf", "PDF"))
    PROCESSING_STATUSES = (
        ("pending", "Pending"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=8, choices=SOURCE_TYPES, blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    position = models.PositiveIntegerField(default=0, db_index=True)
    processing_status = models.CharField(
        max_length=8,
        choices=PROCESSING_STATUSES,
        default="pending",
        db_index=True,
    )
    processing_error = models.TextField(blank=True)
    source_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "-created_at")
        indexes = [models.Index(fields=("is_published", "position"))]

    def __str__(self):
        return self.title


class NotePage(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="pages")
    page_number = models.PositiveIntegerField()
    image_path = models.CharField(max_length=500)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()

    class Meta:
        ordering = ("page_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("note", "page_number"),
                name="unique_note_page_number",
            )
        ]

    def __str__(self):
        return f"{self.note} ? page {self.page_number}"


class ViewLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    page = models.PositiveIntegerField(default=0, help_text="Zero marks opening the note.")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=("user", "timestamp")),
            models.Index(fields=("note", "timestamp")),
        ]

    def __str__(self):
        return f"{self.user} viewed {self.note} at {self.timestamp:%Y-%m-%d %H:%M}"
