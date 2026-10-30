from django.core.management.base import BaseCommand, CommandError

from notes.models import Note
from notes.processing import InvalidNoteFile, process_retained_source


class Command(BaseCommand):
    help = "Process or retry the retained private source for a note."

    def add_arguments(self, parser):
        parser.add_argument("note_id", type=int)

    def handle(self, *args, **options):
        try:
            note = Note.objects.get(pk=options["note_id"])
        except Note.DoesNotExist as exc:
            raise CommandError("Note not found") from exc
        note.processing_status = "pending"
        note.processing_error = ""
        note.save(update_fields=("processing_status", "processing_error"))
        try:
            process_retained_source(note)
        except (InvalidNoteFile, OSError) as exc:
            note.processing_status = "failed"
            note.processing_error = str(exc)
            note.save(update_fields=("processing_status", "processing_error"))
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Processed note {note.pk}."))
