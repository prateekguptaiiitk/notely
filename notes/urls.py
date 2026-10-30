from django.urls import path

from . import views

app_name = "notes"
urlpatterns = [
    path("", views.note_list, name="list"),
    path("n/<slug:slug>/", views.note_detail, name="detail"),
    path("n/<slug:slug>/p/<int:page>/", views.page_image, name="page"),
    path(
        "admin-preview/notes/<int:note_id>/p/<int:page>/",
        views.admin_page_preview,
        name="admin_page_preview",
    ),
]
