import secrets
import string

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User

from .forms import NotelyUserCreationForm


def generate_access_code():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


@admin.action(description="Deactivate selected users")
def deactivate_users(modeladmin, request, queryset):
    queryset.update(is_active=False)


@admin.action(description="Regenerate access codes (shown once)")
def regenerate_access_codes(modeladmin, request, queryset):
    issued = []
    for user in queryset:
        code = generate_access_code()
        user.password = make_password(code)
        user.save(update_fields=["password"])
        issued.append(f"{user.username}: {code}")
    if issued:
        messages.warning(request, "New access codes ? copy now: " + " | ".join(issued))


class NotelyUserAdmin(DjangoUserAdmin):
    add_form = NotelyUserCreationForm
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("username", "is_active")}),)
    list_display = ("username", "is_active", "is_staff", "last_login")
    actions = (deactivate_users, regenerate_access_codes)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            return super().save_model(request, obj, form, change)
        if not change:
            code = generate_access_code()
            obj.set_password(code)
            messages.success(request, f"Access code for {obj.username} (shown once): {code}")
        super().save_model(request, obj, form, change)


admin.site.unregister(User)
admin.site.register(User, NotelyUserAdmin)
