from django.urls import path
from . import views
from .views import helloAPI, voice_search

app_name = 'audiobook'  # audiobook:search


urlpatterns = [
    # 첫 화면
    path('', views.index, name='index'),

    path('test/', views.test, name='test'),

    # 메인화면
    path('main/', views.MainView.as_view(), name='main'),
    path('main/search/', views.main_search, name='main_search'),
    path('api/book/list/', views.BookListAPI.as_view(), name='api_book_list'),
    path('main/genre/', views.MainGenreView.as_view(), name='main_genre'),

    # 청취
    path('content/<int:book_id>', views.ContentHTML.as_view(), name='content'),
    path('content/play/<int:book_id>',
         views.ContentPlayHTML.as_view(), name='content_play'),

    # 성우
    path('voice/custom/', views.VoiceCustomHTML.as_view(), name='voice_custom'),
    path('voice/celebrity/', views.VoiceCelebrityHTML.as_view(),
         name='voice_celebrity'),
    path('voice/custom/upload/', views.voice_custom_upload,
         name='voice_custom_upload'),
    path('voice/custom/complete/', views.voice_custom_complete,
         name='voice_custom_complete'),
    path('voice/custom/complete/upload', views.voice_custom_upload_post,
         name='voice_custom_upload_post'),

    # rvc train
    path('rvc_train/', views.Rvc_Train.as_view(), name='rvc_train'),
    path('rvc_save/', views.Rvc_Save, name='rvc_save'),
    path('rvc_cancel/', views.Rvc_Cancel, name='rvc_cancel'),
    path('tts/', views.TTS, name="TTS")

]
