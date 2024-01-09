import os
import time
import socket

import requests
import paramiko
import pygame
from dotenv import load_dotenv, dotenv_values
import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.urls.base import reverse
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.templatetags.static import static
from django.core.files import File
from django.core.files.storage import default_storage

from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from rest_framework.decorators import api_view
from rest_framework import status
from django.core.files.base import ContentFile
from community.serializers import BookSerializer
from .serializers import VoiceSerializer
from .models import *
from user.views import decode_jwt
from community.models import BookRequest
from config.settings import AWS_S3_CUSTOM_DOMAIN, MEDIA_URL, FILE_SAVE_POINT
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from config.context_processors import get_file_path
from rest_framework.pagination import PageNumberPagination

load_dotenv()
config = dotenv_values(".env")
hostname = config.get("RVC_IP")
username = config.get("RVC_USER")
key_filename = config.get("RVC_KEY")  # 개인 키 파일 경로


def play_wav(file_path):
    pygame.init()
    pygame.mixer.init()
    sound = pygame.mixer.Sound(file_path)
    sound.play()

    # 소리 재생이 끝날 때까지 기다립니다
    while pygame.mixer.get_busy():
        pygame.time.Clock().tick(10)

    pygame.mixer.quit()
    pygame.quit()


def receive_until_prompt(shell, prompt='your_prompt', timeout=30):
    # prompt 문자열이 나타날 때까지 출력을 읽습니다.
    # timeout은 출력이 끝나기를 최대 몇 초간 기다릴지를 정합니다.
    buffer = ''
    shell.settimeout(timeout)  # recv 메소드에 타임아웃을 설정합니다.
    try:
        while not buffer.endswith(prompt):
            response = shell.recv(1024).decode(
                'utf-8', errors='replace')
            buffer += response
    except socket.timeout:
        print("No data received before timeout")
    return buffer

# 첫 화면


def index(request):
    if request.user.is_authenticated:  # 로그인 되어 있으면 main 페이지로 리다이렉트
        return redirect('audiobook:main')

    else:  # 로그인 되어 있지 않으면 index 페이지를 렌더링
        return render(request, 'audiobook/index.html')


def convert_sample_voice(rvc_path):
    sample_voice_path = ''
    return sample_voice_path

# 메인화면


class MainView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/main.html'

    def get(self, request):
        # 이달의 TOP 10 책
        top_books = Book.objects.all().order_by('-book_likes')[:10]

        # 최근 이용한 책
        user_history_book = []  # 최신 이용한 책 순서로 보이기 위해서 filter를 사용하지 않고 리스트를 만들어서 사용
        if isinstance(request.user, AnonymousUser):
            user_history_book = []
        else:
            for book_id in request.user.user_book_history:
                book = get_object_or_404(Book, book_id=book_id)
                user_history_book.append(book)

        # 이달의 TOP 10 음성
        top_voices = Voice.objects.all().order_by('-voice_like')[:10]

        # 좋아요 로직
        user = request.user

        if isinstance(user, AnonymousUser):
            user_favorites = []
        else:
            user_favorites = user.user_favorite_books
            if user_favorites is None:
                user_favorites = []  # None으로 처리되면 template에서 인식하지 못하므로, 빈 값으로 처리

        context = {
            'top_books': top_books,
            'user_history_book': user_history_book,
            'top_voices': top_voices,
            'user': request.user,
            'user_favorites': user_favorites,
        }

        return Response(context, template_name=self.template_name)


PAGE_SIZE = 12  # Number of items per page


def main_search(request):
    query = request.GET.get('query', '')
    book_list = Book.objects.filter(
        Q(book_title__icontains=query) | Q(book_author__icontains=query))[:PAGE_SIZE]
    serializer = BookSerializer(book_list, many=True)

    # 좋아요 로직
    user = request.user

    if isinstance(user, AnonymousUser):
        user_favorites = []
    else:
        user_favorites = user.user_favorite_books
        if user_favorites is None:
            user_favorites = []  # None으로 처리되면 template에서 인식하지 못하므로, 빈 값으로 처리

    context = {
        'book_list': serializer.data,
        'user_favorites': user_favorites,
    }

    return render(request, 'audiobook/main_search.html', context)


class CustomPaginationClass(PageNumberPagination):
    page_size = PAGE_SIZE


class BookListAPI(ListAPIView):
    serializer_class = BookSerializer
    pagination_class = CustomPaginationClass

    def get_queryset(self):
        query = self.request.query_params.get('query', '')
        queryset = Book.objects.filter(
            Q(book_title__icontains=query) | Q(book_author__icontains=query)
        ).order_by('-book_likes', 'book_id')

        return queryset


class MainGenreView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/main_genre.html'

    def get(self, request):
        categories = {
            '소설': Book.objects.filter(book_genre='novel').order_by('-book_likes')[:10],
            '인문': Book.objects.filter(book_genre='humanities').order_by('-book_likes')[:10],
            '자연과학': Book.objects.filter(book_genre='nature').order_by('-book_likes')[:10],
            '자기계발': Book.objects.filter(book_genre='self_improvement').order_by('-book_likes')[:10],
            '아동': Book.objects.filter(book_genre='children').order_by('-book_likes')[:10],
            '기타': Book.objects.filter(book_genre='etc').order_by('-book_likes')[:10],
        }

        # 좋아요 로직
        user = request.user

        if isinstance(user, AnonymousUser):
            user_favorites = []
        else:
            user_favorites = user.user_favorite_books
            if user_favorites is None:
                user_favorites = []  # None으로 처리되면 template에서 인식하지 못하므로, 빈 값으로 처리

        context = {
            'categories': categories,
            'user_favorites': user_favorites,
        }

        return Response(context, template_name=self.template_name)


def genre(request):
    pass


def search(request):
    pass

# 청취


class ContentHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/content.html'

    def get(self, request, book_id):
        file_path = get_file_path()
        book = get_object_or_404(Book, pk=book_id)

        # 쿠키에서 성우 정보 읽기
        selected_voice_id = request.COOKIES.get('selectedVoiceId')
        print(selected_voice_id)
        selected_voice = None

        if selected_voice_id:
            try:
                selected_voice = Voice.objects.get(pk=selected_voice_id)
            except Voice.DoesNotExist:
                print("Selected voice does not exist.")

        if request.user.is_authenticated:
            user_book_history = request.user.user_book_history
            user = request.user
        else:
            user = {
                'user_id': 1,
            }
            user_book_history = []

        context = {
            'result': True,
            'book': book,
            'file_path': file_path,
            'user_book_history': user_book_history,
            'selected_voice': selected_voice,
            'user': user,
        }
        return Response(context, template_name=self.template_name)


@method_decorator(login_required(login_url='user:login'), name='dispatch')
class ContentPlayHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/content_play.html'

    def get(self, request, book_id):
        try:
            book = Book.objects.get(pk=book_id)
            voice_name = request.GET.get("voice_name")

        except Book.DoesNotExist:
            print('book not exist.')
            return Response(status=404, template_name=self.template_name)

        user_favorite_books = [
        ] if request.user.user_favorite_books is None else request.user.user_favorite_books
        context = {
            'result': True,
            'book': book,
            'voice_name': voice_name,
            'user': request.user,
            'user_favorites': user_favorite_books
        }
        print(user_favorite_books)
        return Response(context, template_name=self.template_name)

    def post(self, request, book_id):
        data = request.data

        if 'selectedVoiceId' in request.COOKIES:
            # 선택된 쿠키가 존재하는 경우
            selected_voice_id = request.COOKIES.get('selectedVoiceId')
            print("came in")
            print(f"selectedVoiceId 쿠키 값: {selected_voice_id}")
        else:
            # 선택된 쿠키가 존재하지 않는 경우
            selected_voice_id = 1  # 또는 다른 기본값을 할당할 수 있습니다.
            # 이에 따른 추가적인 처리를 수행할 수 있습니다.

        tone = data.get('tone', 0)
        text = "안녕하세요"
        voice = Voice.objects.get(
            pk=selected_voice_id)
        voice_name = voice.voice_name
        file_path = get_file_path()
        file_path = "C:/S3_bucket/voice_rvcs/" + voice_name + ".pth"
        print(file_path)

        # SSH 클라이언트 생성
        client = paramiko.SSHClient()
        # 호스트 키 자동으로 수락
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # SSH 연결 (키 기반 인증)
        client.connect(hostname=hostname, username=username,
                       key_filename=key_filename)

        sftp = client.open_sftp()

        # 파일을 전송할 원격 경로
        remote_file_path = f'/home/kimyea0454/project-main/assets/weights/{voice_name}.pth'

        # 파일 전송
        sftp.put(file_path, remote_file_path)

        # 셸 세션 열기
        shell = client.invoke_shell()

        commands = [
            f'python3 tts.py {text}\n',
            'cd project-main\n',
            f'python3 inference.py {voice_name} {tone} audios/tts.mp3\n',
            'rm -rf audios/tts.mp3\n',
            f'rm -rf assets/weights/{voice_name}.pth\n',
        ]

        for cmd in commands:
            shell.send(cmd)
            # 각 명령의 실행이 끝날 때까지 기다립니다.
            output = receive_until_prompt(shell, prompt='$ ')
            print(output)  # 받은 출력을 표시합니다.

        # 임시 저장한 로컬 파일을 원격 시스템으로 업로드
        remote_path = f'/home/kimyea0454/project-main/audios/{voice_name}.mp3'
        project_path = os.getcwd()
        folder_path = os.path.join(project_path, 'static', 'temp')  # 경로 조합
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        sftp.get(remote_path, os.path.join(
            project_path, f'static/temp/{voice_name}.mp3'))
        # SFTP 세션 종료
        sftp.close()
        client.close()

        return JsonResponse({'Good': '변환완료'}, status=200)


# 성우
@method_decorator(login_required(login_url='user:login'), name='dispatch')
class VoiceCustomHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/voice_custom.html'

    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        user_inform = decode_jwt(request.COOKIES.get("jwt"))
        user = User.objects.get(user_id=user_inform['user_id'])

        user_favorite_voice = user.user_favorite_voices
        user_voices = Voice.objects.filter(user=user).order_by('voice_id')
        public_voices = Voice.objects.filter(
            voice_is_public=True).exclude(user=user).order_by('voice_id')

        search_term = request.GET.get('search_term')
        if search_term:
            user_voices = user_voices.filter(voice_name__icontains=search_term)
            public_voices = public_voices.filter(
                voice_name__icontains=search_term)

        context = {
            'active_tab': 'voice_private',
            'user_voices': user_voices,
            'public_voices': public_voices,
            'user_favorites': user_favorite_voice,
            'book': book
        }

        return Response(context, template_name=self.template_name)


@method_decorator(login_required(login_url='user:login'), name='dispatch')
class VoiceCelebrityHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/voice_celebrity.html'

    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        user_favorite_voices = request.user.user_favorite_voices
        
        user_favorite_voices = Voice.objects.filter(
            voice_id__in=user_favorite_voices)

        search_term = request.GET.get('search_term')
        if search_term:
            user_favorite_voices = user_favorite_voices.filter(
                voice_name__icontains=search_term)
        top_10_voices = user_favorite_voices.order_by('-voice_like')[:10]

        context = {
            'active_tab': 'voice_popular',
            'user_favorite_voices': user_favorite_voices,
            'top_10_voices': top_10_voices,
            'book': book
        }
        return Response(context, template_name=self.template_name)


class voice_custom_upload(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/voice_custom_upload.html'

    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)

        try:
            context = {
                'book': book
            }
            return Response(context, template_name=self.template_name)
        except:
            return Response(status=404, template_name=self.template_name)

    def post(self, request, book_id):
        data = request.data
        book = get_object_or_404(Book, pk=book_id)

        # 이름 중복 검사
        if 'voice_name' in data and 'voice_photo' not in data and 'voice_file' not in data:
            voice_name = data['voice_name']
            if Voice.objects.filter(voice_name=voice_name).exists():
                return JsonResponse({'message': '이미 존재하는 이름입니다.'}, status=200)
            else:
                return JsonResponse({'message': '사용 가능한 이름입니다.'}, status=200)

        # Voice 인스턴스 생성
        elif 'voice_name' in data and 'voice_photo' in data and 'voice_file' in data:
            voice_name = data['voice_name']
            voice_photo = request.FILES['voice_photo']
            voice_file = request.FILES['voice_file']  # client에서 받아온 mp3 파일
            print(voice_photo)
            print(voice_file)

            if Voice.objects.filter(voice_name=voice_name).exists():
                return JsonResponse({'error': '이미 존재하는 이름입니다.'}, status=400)

            # mp3를 rvc로 바꾸는 로직
            # SSH 클라이언트 생성
            client = paramiko.SSHClient()
            # 호스트 키 자동으로 수락
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # SSH 연결 (키 기반 인증)
            client.connect(hostname=hostname, username=username,
                           key_filename=key_filename)

            # 셸 세션 열기
            shell = client.invoke_shell()

            commands = [
                'ls\n',
                'cd project-main\n',
                'rm -rf voices\n',
                'mkdir voices\n',
                'cd assets\n',
                'rm -rf weights\n',
                'mkdir weights\n',
                'cd ..\n',
            ]

            for cmd in commands:
                shell.send(cmd)
                # 각 명령의 실행이 끝날 때까지 기다립니다.
                output = receive_until_prompt(shell, prompt='$ ')
                print(output)  # 받은 출력을 표시합니다.

            # SFTP 클라이언트 시작
            sftp_client = client.open_sftp()

            # 임시 저장한 로컬 파일을 원격 시스템으로 업로드
            remote_rvc_path = f'/home/kimyea0454/project-main/voices/{voice_name}.mp3'

            sftp_client.putfo(voice_file, remote_rvc_path)

            # SFTP 세션 종료
            sftp_client.close()

            commands = [
                f'python3 preprocess.py {voice_name}\n',
                f'python3 extract_features.py {voice_name}\n',
                f'python3 train_index.py {voice_name}\n',
                'pwd\n',
                f'python3 train_model.py {voice_name}\n'
            ]

            for cmd in commands:
                shell.send(cmd)
                # 각 명령의 실행이 끝날 때까지 대기
                output = receive_until_prompt(shell, prompt='$ ')
                print('output:', output)  # 받은 출력을 표시

            # 연결 종료
            client.close()

            # 파일을 임시 디렉토리에 저장(image, rvc)
            temp_voice = TemporaryFile.objects.create(
                temp_voice_image_path=voice_photo,
            )
            print(temp_voice)

            # 세션에 데이터 저장(name 및 image, rvc의 id 값)
            request.session['voice_creation'] = {
                'voice_name': voice_name,
                'temp_voice_image_path': temp_voice.id  # 이미지 파일의 id을 세션에 저장
            }

            redirect_url = reverse('audiobook:voice_custom_complete', kwargs={
                                   'book_id': book_id})
            return JsonResponse({'redirect_url': redirect_url})
        else:
            return JsonResponse({'error': '잘못된 요청입니다.'}, status=400)


class voice_custom_complete(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/voice_custom_complete.html'

    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        voice_creation_data = request.session.get(
            'voice_creation')  # 세션에서 데이터를 가져옴

        context = {
            'book': book
        }

        if voice_creation_data:
            voice_name = voice_creation_data['voice_name']
            context['voice_name'] = voice_name  # 세션 데이터를 뷰로 넘겨줌

        try:
            return Response(context, template_name=self.template_name)
        except:
            return Response(status=404, template_name=self.template_name)

    def post(self, request, book_id):
        data = request.data
        action = data.get('action')

        voice_creation_data = request.session.get('voice_creation')  # 세션 데이터

        if action == 'play':
            # 'Play'를 누르면 text랑 tone을 넘겨 받음
            tts_text = data.get('tts_text', '')
            tone = data.get('tone', 0)
            print("TTS Text:", tts_text)
            print("Tone:", tone)
            text = data.get('tts_text', '').replace(' ', '')
            voice_name = voice_creation_data.get('voice_name')

            # SSH 클라이언트 생성
            client = paramiko.SSHClient()
            # 호스트 키 자동으로 수락
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # SSH 연결 (키 기반 인증)
            client.connect(hostname=hostname, username=username,
                           key_filename=key_filename)

            # 셸 세션 열기
            shell = client.invoke_shell()

            commands = [
                f'python3 tts.py {text}\n',
                'cd project-main\n',
                f'python3 inference.py {voice_name} {tone} audios/tts.mp3\n',
                'rm -rf audios/tts.mp3\n',
            ]

            for cmd in commands:
                shell.send(cmd)
                # 각 명령의 실행이 끝날 때까지 기다립니다.
                output = receive_until_prompt(shell, prompt='$ ')
                print(output)  # 받은 출력을 표시합니다.

            sftp_client = client.open_sftp()

            # 임시 저장한 로컬 파일을 원격 시스템으로 업로드
            remote_path = f'/home/kimyea0454/project-main/audios/{voice_name}.mp3'
            project_path = os.getcwd()
            folder_path = os.path.join(project_path, 'static', 'tts')  # 경로 조합
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            sftp_client.get(remote_path, os.path.join(
                project_path, f'static/tts/{voice_name}.mp3'))
            # SFTP 세션 종료
            sftp_client.close()

            wav_file_path = os.path.join(
                project_path, f'static/tts/{voice_name}.mp3')
            play_wav(wav_file_path)
            os.remove(os.path.join(project_path,
                      f'static/tts/{voice_name}.mp3'))

            return JsonResponse({'status': 'TTS processed'})

        elif action == 'save':
            voice_creation_data = request.session.get(
                'voice_creation')  # 세션 데이터

            if voice_creation_data:
                voice_name = voice_creation_data['voice_name']
                voice_id = voice_creation_data['temp_voice_image_path']
                voice_image = TemporaryFile.objects.get(pk=voice_id)
                public_status = data.get('public') == 'true'
                tone = data.get('tone')

                # param 조정된 rvc를 voice_path에 저장
                # SSH 클라이언트 생성
                client = paramiko.SSHClient()
                # 호스트 키 자동으로 수락
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                # SSH 연결 (키 기반 인증)
                client.connect(hostname=hostname, username=username,
                               key_filename=key_filename)

                # 셸 세션 열기
                shell = client.invoke_shell()

                sample = "안녕하세요. 오디 많은 이용 부탁드려요."
                commands = [
                    f'python3 tts.py {sample}\n',
                    'cd project-main\n',
                    f'python3 inference.py {voice_name} {tone} audios/tts.mp3\n',
                    'rm -rf audios/tts.mp3\n',
                ]

                for cmd in commands:
                    shell.send(cmd)
                    # 각 명령의 실행이 끝날 때까지 기다립니다.
                    output = receive_until_prompt(shell, prompt='$ ')
                    print(output)  # 받은 출력을 표시합니다.

                sftp_client = client.open_sftp()
                # 임시 저장한 로컬 파일을 원격 시스템으로 업로드
                remote_path = f'/home/kimyea0454/project-main/audios/{voice_name}.mp3'
                project_path = os.getcwd()
                folder_path = os.path.join(
                    project_path, 'static', 'tts')  # 경로 조합
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                    print(f"폴더가 생성되었습니다: {folder_path}")
                else:
                    print(f"이미 해당 폴더가 존재합니다: {folder_path}")

                # 샘플 오디오 가져와서 static/tts에 저장
                sftp_client.get(remote_path, os.path.join(
                    project_path, f'static/tts/{voice_name}.mp3'))

                # 모델 가져와서 static/tts에 저장
                remote_path = f'/home/kimyea0454/project-main/assets/weights/{voice_name}.pth'
                sftp_client.get(remote_path, os.path.join(
                    project_path, f'static/tts/{voice_name}.pth'))

                # SFTP 세션 종료
                sftp_client.close()

                # Voice 인스턴스 생성 및 저장
                voice_data = {
                    'voice_name': voice_name,  # 사용자 입력
                    'voice_like': 0,
                    # 'voice_path': voice_name,
                    'voice_image_path': voice_image.temp_voice_image_path,
                    # 'voice_sample_path': 'test',
                    'voice_created_date': datetime.date.today(),
                    'voice_is_public':  public_status,
                    'user': request.user.user_id,
                }

                project_path = os.getcwd()
                with open(os.path.join(project_path, f'static/tts/{voice_name}.mp3'), 'rb') as file:
                    voice_sample = ContentFile(file.read())
                with open(f'static/tts/{voice_name}.pth', 'rb') as file:
                    voice_model = ContentFile(file.read())

                print("staic/tts 파일 로딩 완료")

                serializer = VoiceSerializer(data=voice_data)
                if serializer.is_valid():
                    voice_instance = serializer.save()
                    print("voice 인스턴스 생성 완료")
                    voice_instance.voice_sample_path.save(
                        f"{voice_name}.mp3", voice_sample, save=False)
                    voice_instance.voice_path.save(
                        f"{voice_name}.pth", voice_model, save=False)
                    voice_instance.save()

                else:
                    print(serializer.errors)
                    return Response({
                        'status': 'error',
                        'message': 'Registration failed.',
                        'errors': serializer.errors
                    }, status=501)

                del request.session['voice_creation']

                # static/tts에 있는 파일 삭제
                os.remove(os.path.join(project_path,
                          f'static/tts/{voice_name}.mp3'))
                os.remove(os.path.join(project_path,
                          f'static/tts/{voice_name}.pth'))

                commands = [
                    f'rm -rf assets/weights/{voice_name}.pth\n',
                    f'rm -rf audios/{voice_name}.wav\n',
                    f'rm -rf logs/{voice_name}\n',
                    'rm -rf voices\n',
                    'mkdir voices\n',
                ]

                for cmd in commands:
                    shell.send(cmd)
                    # 각 명령의 실행이 끝날 때까지 기다림
                    output = receive_until_prompt(shell, prompt='$ ')
                    print(output)

                # 연결 종료
                client.close()

                voice_image.delete()

                redirect_url = reverse('audiobook:voice_custom', kwargs={
                                       'book_id': book_id})
                return JsonResponse({'redirect_url': redirect_url})

        else:
            voice_creation_data = request.session.get(
                'voice_creation')  # 세션 데이터

            if voice_creation_data:
                voice_name = voice_creation_data['voice_name']
                temp_voice_photo_id = voice_creation_data['temp_voice_photo_id']
                # SSH 클라이언트 생성
                client = paramiko.SSHClient()
                # 호스트 키 자동으로 수락
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                # SSH 연결 (키 기반 인증)
                client.connect(hostname=hostname, username=username,
                               key_filename=key_filename)

                temp_voice_photo = TemporaryFile.objects.get(
                    id=temp_voice_photo_id)

                voice_image.delete()

                # 셸 세션 열기
                shell = client.invoke_shell()

                commands = [
                    'cd project-main\n',
                    f'rm -rf assets/weights/{voice_name}.pth\n',
                    f'rm -rf audios/{voice_name}.mp3\n',
                    f'rm -rf logs/{voice_name}\n',
                    'rm -rf voices\n',
                    'mkdir voices\n',
                ]

                for cmd in commands:
                    shell.send(cmd)
                    # 각 명령의 실행이 끝날 때까지 기다립니다.
                    output = receive_until_prompt(shell, prompt='$ ')
                    print(output)  # 받은 출력을 표시합니다.

                client.close()
                redirect_url = reverse('audiobook:voice_custom_upload', kwargs={
                                       'book_id': book_id})
                return JsonResponse({'redirect_url': redirect_url})


def voice_custom_upload_post(request):
    return render(request, 'audiobook/voice_custom.html')


@api_view(['GET'])
def helloAPI(request):
    return Response("hello world!")


class VoiceLikeView(APIView):
    renderer_classes = [TemplateHTMLRenderer]

    def get(self, request):
        user_inform = decode_jwt(request.COOKIES.get("jwt"))
        user = User.objects.get(user_id=user_inform['user_id'])
        voice_id = int(request.GET.get('voice_id'))  
        voice = Voice.objects.get(voice_id = voice_id)
        
        if voice_id in map(int, user.user_favorite_voices):
            user.user_favorite_voices.remove(voice_id)
            voice.voice_like -= 1
            print(f"성우 이름 : {voice.voice_name}, voice_id : {voice.voice_id} 좋아요 취소함")
        else:
            user.user_favorite_voices.append(voice_id)
            voice.voice_like += 1
            print(f"성우 이름 : {voice.voice_name}, voice_id : {voice.voice_id} 좋아요 완료함")
                
        user.save()
        voice.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})


@api_view(["GET", "POST"])
def voice_search(request):
    if request.method == 'GET':
        voices = Voice.objects.all()
        serializer = VoiceSerializer(voices, many=True)
        return redirect('audiobook:voice_custom_complete')

        # return Response(serializer.data)

    elif request.method == 'POST':
        serializer = VoiceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            # print(serializer.data, status.HTTP_201_CREATED)
            # return redirect('audiobook:voice_custom_complete')
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# 중복찾기


class Voice_Custom_Search(View):
    def get(self, request):
        voice_name = request.GET.get('voice_name', None)
        print("i got", voice_name)

        if voice_name is None:
            return JsonResponse({'error': 'voice_name parameter is required.'})

        # Voice 모델에서 voice_name 값이 일치하는 객체 찾기
        try:
            voice = Voice.objects.get(voice_name=voice_name)
            print(voice)
            return JsonResponse({'check': 'True'})
        except Voice.DoesNotExist:
            return JsonResponse({'check': 'False'})
