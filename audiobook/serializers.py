from rest_framework import serializers
from .models import Voice



class VoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voice
        fields = ["voice_name", "voice_like", "voice_path", "voice_image_path", "voice_is_public", "user"]