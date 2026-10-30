from django import forms
from django.conf import settings

from .models import Note
from .processing import InvalidNoteFile, read_upload, validate_content


class NoteAdminForm(forms.ModelForm):
    upload = forms.FileField(
        required=False,
        help_text="PNG, JPG, JPEG or PDF. The original stays in private storage.",
    )

    class Meta:
        model = Note
        fields = (
            "title",
            "slug",
            "description",
            "source_type",
            "is_published",
            "position",
            "upload",
        )

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        if not upload:
            return upload
        if upload.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(
                f"Maximum upload size is {settings.MAX_UPLOAD_MB} MB."
            )
        try:
            content = read_upload(upload)
            validate_content(upload.name, content)
        except InvalidNoteFile as exc:
            raise forms.ValidationError(str(exc)) from exc
        return upload
