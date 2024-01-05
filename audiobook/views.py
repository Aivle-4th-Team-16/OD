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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from rest_framework.decorators import api_view
from rest_framework import status
from django.core.files.base import ContentFile

from .serializers import VoiceSerializer
from .models import *
from user.views import decode_jwt
from community.models import BookRequest
from config.settings import AWS_S3_CUSTOM_DOMAIN, MEDIA_URL, FILE_SAVE_POINT
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from config.context_processors import get_file_path

load_dotenv()


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

# 첫 화면
def index(request):
    if request.user.is_authenticated:  # 로그인 되어 있으면 main 페이지로 리다이렉트
        return redirect('audiobook:main')

    else:  # 로그인 되어 있지 않으면 index 페이지를 렌더링
        return render(request, 'audiobook/index.html')

def test(request):
    return render(request, 'audiobook/ddd.html')

# 메인화면
def convert_sample_voice(rvc_path):
    sample_voice_path = ''
    return sample_voice_path

class MainView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/main.html'

    def get(self, request):
        # 이달의 TOP 10 책
        top_books = Book.objects.all().order_by('-book_likes')[:10]

        # 최근 이용한 책
        user_history_book = []  # 최신 이용한 책 순서로 보이기 위해서 filter를 사용하지 않고 리스트를 만들어서 사용
        if request.user.user_book_history is not None:
            for book_id in request.user.user_book_history:
                book = get_object_or_404(Book, book_id=book_id)
                user_history_book.append(book)

        # 이달의 TOP 10 음성
        top_voices = Voice.objects.all().order_by('-voice_like')[:10]
        # AI 기능 구현 이후
        # for voice in top_voices:
        # voice.voice_sample_path = convert_sample_voice(voice.voice_path) # 객체 속성(필드) 동적 추가
        # voice.voice_sample_path = static('voices/voice_sample.mp3')

        context = {
            'top_books': top_books,
            'user_history_book': user_history_book,
            'top_voices': top_voices,
            'user': request.user,
        }

        return Response(context, template_name=self.template_name)


class MainSearchView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/main_search.html'

    def get(self, request):
        query = request.query_params.get('query', '')
        book_list = Book.objects.filter(
            Q(book_title__icontains=query) | Q(book_author__icontains=query))

        return Response({'book_list': book_list})


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

        return Response({'categories': categories})

# RvcTrain


class Rvc_Train(APIView):
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    template_name = 'audiobook/voice_custom_complete.html'

    def get(self, request):
        return Response({'result': False, 'message': 'GET 요청은 허용되지 않습니다.'})

    def post(self, request):
        print(request.data)

        config = dotenv_values(".env")
        hostname = config.get("RVC_IP")
        username = config.get("RVC_USER")
        key_filename = config.get("RVC_KEY")  # 개인 키 파일 경로

        voice_file = request.FILES['voice_file']
        voice_name = request.POST['voice_name']

        # SSH 클라이언트 생성
        client = paramiko.SSHClient()
        # 호스트 키 자동으로 수락
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # SSH 연결 (키 기반 인증)
        client.connect(hostname=hostname, username=username,
                       key_filename=key_filename)

        # 셸 세션 열기
        shell = client.invoke_shell()

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
        remote_path = f'/home/kimyea0454/project-main/voices/{voice_name}.mp3'
        sftp_client.putfo(voice_file, remote_path)
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
            # 각 명령의 실행이 끝날 때까지 기다립니다.
            output = receive_until_prompt(shell, prompt='$ ')
            print(output)  # 받은 출력을 표시합니다.

        # 연결 종료
        client.close()

        return Response(template_name=self.template_name)

# TTS


@api_view(["POST"])
def TTS(request):
    config = dotenv_values(".env")
    hostname = config.get("RVC_IP")
    username = config.get("RVC_USER")
    key_filename = config.get("RVC_KEY")  # 개인 키 파일 경로

    voice_name = request.POST['voice_name']
    tone = request.POST['tone']
    text = request.POST['text']
    print(tone, text)

    # SSH 클라이언트 생성
    client = paramiko.SSHClient()
    # 호스트 키 자동으로 수락
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # SSH 연결 (키 기반 인증)
    client.connect(hostname=hostname, username=username,
                   key_filename=key_filename)

    # 셸 세션 열기
    shell = client.invoke_shell()

    def receive_until_prompt(shell, prompt='your_prompt', timeout=30):
        # prompt 문자열이 나타날 때까지 출력을 읽습니다.
        # timeout은 출력이 끝나기를 최대 몇 초간 기다릴지를 정합니다.
        buffer = ''
        shell.settimeout(timeout)  # recv 메소드에 타임아웃을 설정합니다.
        try:
            while not buffer.endswith(prompt):
                response = shell.recv(1024).decode('utf-8', errors='replace')
                buffer += response
        except socket.timeout:
            print("No data received before timeout")
        return buffer

    commands = [
        f'python3 tts.py {text}\n',
        'cd project-main\n',
        f'python3 inference.py {voice_name} {tone} audios/tts.mp3\n',
        'rm -rf audios/tts.mp3\n',
    ]

    try:
        for cmd in commands:
            shell.send(cmd)
            # 각 명령의 실행이 끝날 때까지 기다립니다.
            output = receive_until_prompt(shell, prompt='$ ')
            print(output)  # 받은 출력을 표시합니다.

        sftp_client = client.open_sftp()

        # 임시 저장한 로컬 파일을 원격 시스템으로 업로드
        remote_path = f'/home/kimyea0454/project-main/audios/{voice_name}.wav'
        project_path = os.getcwd()
        sftp_client.get(remote_path, os.path.join(
            project_path, f'static/tts/{voice_name}.mp3'))
        # SFTP 세션 종료
        sftp_client.close()

        wav_file_path = os.path.join(
            project_path, f'static/tts/{voice_name}.mp3')
        play_wav(wav_file_path)
        os.remove(os.path.join(project_path, f'static/tts/{voice_name}.mp3'))

        return Response("Well funciotned", status=status.HTTP_200_OK)
    except:
        return Response("WRONG", status=status.HTTP_400_BAD_REQUEST)

# 저장하기


@api_view(["POST"])
def Rvc_Save(request):

    print(request.data)
    voice_name = request.POST['voice_name']
    tone = request.POST['tone']

    config = dotenv_values(".env")
    hostname = config.get("RVC_IP")
    username = config.get("RVC_USER")
    key_filename = config.get("RVC_KEY")  # 개인 키 파일 경로

    # SSH 클라이언트 생성
    client = paramiko.SSHClient()
    # 호스트 키 자동으로 수락
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # SSH 연결 (키 기반 인증)
    client.connect(hostname=hostname, username=username,
                   key_filename=key_filename)

    # 셸 세션 열기
    shell = client.invoke_shell()

    def receive_until_prompt(shell, prompt='your_prompt', timeout=30):
        # prompt 문자열이 나타날 때까지 출력을 읽습니다.
        # timeout은 출력이 끝나기를 최대 몇 초간 기다릴지를 정합니다.
        buffer = ''
        shell.settimeout(timeout)  # recv 메소드에 타임아웃을 설정합니다.
        try:
            while not buffer.endswith(prompt):
                response = shell.recv(1024).decode('utf-8', errors='replace')
                buffer += response
        except socket.timeout:
            print("No data received before timeout")
        return buffer

    sample = "안녕?난오디야"
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
    remote_path = f'/home/kimyea0454/project-main/audios/{voice_name}.wav'
    project_path = os.getcwd()
    folder_path = os.path.join(project_path, 'static', 'tts')  # 경로 조합
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"폴더가 생성되었습니다: {folder_path}")
    else:
        print(f"이미 해당 폴더가 존재합니다: {folder_path}")
        
    sftp_client.get(remote_path, os.path.join(project_path, f'static/tts/{voice_name}.mp3'))
    
    remote_path = f'/home/kimyea0454/project-main/assets/weights/{voice_name}.pth'
    sftp_client.get(remote_path, os.path.join(
        project_path, f'static/tts/{voice_name}.pth'))
    # SFTP 세션 종료
    sftp_client.close()

    voice_data = {
        'voice_name': voice_name,  # 사용자 입력
        'voice_like': 0,
        #'voice_path': voice_name,
        #'voice_image_path': voice_name,
        #'voice_sample_path': 'test',
        'voice_created_date': datetime.date.today(),
        'voice_is_public':  request.POST['voice_public'],
        'user': request.user.user_id,
    }
    
    with open(os.path.join(project_path, f'static/tts/{voice_name}.mp3'), 'rb') as file:
        voice_sample = ContentFile(file.read())
    voice_image = ContentFile(request.FILES['voice_image'].read())
    with open(f'static/tts/{voice_name}.pth', 'rb') as file:
        voice_model = ContentFile(file.read())

    serializer = VoiceSerializer(data=voice_data)
    if serializer.is_valid():
        voice_instance = serializer.save()
        voice_instance.voice_image_path.save(
            f"{voice_name}.jpg", voice_image, save=False)
        voice_instance.voice_sample_path.save(
            f"{voice_name}.mp3", voice_sample, save=False)
        voice_instance.voice_path.save(
            f"{voice_name}.pth", voice_model, save=False)
        voice_instance.save()

    else:
        # print(serializer.errors)
        return Response({
            'status': 'error',
            'message': 'Registration failed.',
            'errors': serializer.errors
        }, status=501)

    os.remove(os.path.join(project_path, f'static/tts/{voice_name}.mp3'))
    os.remove(os.path.join(project_path, f'static/tts/{voice_name}.pth'))

    commands = [
        f'rm -rf assets/weights/{voice_name}.pth\n',
        f'rm -rf audios/{voice_name}.wav\n',
        f'rm -rf logs/{voice_name}\n',
        'rm -rf voices\n',
        'mkdir voices\n',
    ]

    for cmd in commands:
        shell.send(cmd)
        # 각 명령의 실행이 끝날 때까지 기다립니다.
        output = receive_until_prompt(shell, prompt='$ ')
        print(output)  # 받은 출력을 표시합니다.

    # 연결 종료
    client.close()

    return Response({
        'status': 'accepted',
        'message': '성공'
    }, status=200)


@api_view(["POST"])
def Rvc_Cancel(request):
    print(request.data)
    voice_name = request.POST['voice_name']

    config = dotenv_values(".env")
    hostname = config.get("RVC_IP")
    username = config.get("RVC_USER")
    key_filename = config.get("RVC_KEY")  # 개인 키 파일 경로

    # SSH 클라이언트 생성
    client = paramiko.SSHClient()
    # 호스트 키 자동으로 수락
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # SSH 연결 (키 기반 인증)
    client.connect(hostname=hostname, username=username,
                   key_filename=key_filename)

    # 셸 세션 열기
    shell = client.invoke_shell()

    def receive_until_prompt(shell, prompt='your_prompt', timeout=30):
        # prompt 문자열이 나타날 때까지 출력을 읽습니다.
        # timeout은 출력이 끝나기를 최대 몇 초간 기다릴지를 정합니다.
        buffer = ''
        shell.settimeout(timeout)  # recv 메소드에 타임아웃을 설정합니다.
        try:
            while not buffer.endswith(prompt):
                response = shell.recv(1024).decode('utf-8', errors='replace')
                buffer += response
        except socket.timeout:
            print("No data received before timeout")
        return buffer

    commands = [
        'cd project-main\n',
        f'rm -rf assets/weights/{voice_name}.pth\n',
        f'rm -rf audios/{voice_name}.wav\n',
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
    return Response({
        'status': 'accepted',
        'message': '성공'
    }, status=200)


def genre(request):
    pass


def search(request):
    pass


# 청취
class ContentHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/content.html'

    def get(self, request, book_id):
        voice_name = request.GET.get("voice_name")
        file_path = get_file_path()
        book = get_object_or_404(Book, pk=book_id)
        if request.user.is_authenticated:
            print('로그인')
            tmp = request.user.user_book_history
            user_book_history = [] if tmp is None else tmp
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
            'voice_name': voice_name,
            'user_book_history': user_book_history,
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
            
            if FILE_SAVE_POINT == 'local':
                model_path = f'C:\\S3_bucket\\voice_rvcs\\{voice_name}.pth'
            else:
                model_path = 0
                
            # config = dotenv_values(".env")
            # hostname = config.get("RVC_IP")
            # username = config.get("RVC_USER")
            # key_filename = config.get("RVC_KEY")  # 개인 키 파일 경로

            # # SSH 클라이언트 생성
            # client = paramiko.SSHClient()
            # # 호스트 키 자동으로 수락
            # client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # # SSH 연결 (키 기반 인증)
            # client.connect(hostname=hostname, username=username, key_filename=key_filename)

            '''
            try:
                sftp = client.open_sftp()
                
                # 파일을 전송할 원격 경로
                remote_file_path = f'/home/kimyea0454/project-main/assets/weights/{voice_name}.pth'

                # 파일 전송
                sftp.put(model_path, remote_file_path)

                # 연결 종료
                sftp.close()
            except:
                return Response(status=405, template_name=self.template_name)
            '''

            '''
            # 셸 세션 열기
            shell = client.invoke_shell()

            def receive_until_prompt(shell, prompt='your_prompt', timeout=30):
                # prompt 문자열이 나타날 때까지 출력을 읽습니다.
                # timeout은 출력이 끝나기를 최대 몇 초간 기다릴지를 정합니다.
                buffer = ''
                shell.settimeout(timeout)  # recv 메소드에 타임아웃을 설정합니다.
                try:
                    while not buffer.endswith(prompt):
                        response = shell.recv(1024).decode('utf-8',errors='replace')
                        buffer += response
                except socket.timeout:
                    print("No data received before timeout")
                return buffer
            '''
            # client.close()
            
            
        except Book.DoesNotExist:
            print('book not exist.')
            return Response(status=404, template_name=self.template_name)
        user_favorite_books = [] if request.user.user_favorite_books is None else request.user.user_favorite_books
        context = {
            'result': True,
            'book': book,
            'voice_name': voice_name,
            'user': request.user,
            'user_favorites': user_favorite_books
        }
        print(context)
        return Response(context, template_name=self.template_name)

# 성우
@method_decorator(login_required(login_url='user:login'), name='dispatch')
class VoiceCustomHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/voice_custom.html'
    
    def get(self, request, book_id):
        user_id = request.user.user_id
        print("user_id is",user_id)
        print("book id is",book_id)

        # Voice 모델에서 voice_name 값이 일치하는 객체 찾기
        try:
            voices_with_user_id = Voice.objects.filter(user_id=user_id)
            voices_without_user_id = Voice.objects.exclude(user_id=user_id)
            voice_names1 = [voice.voice_name for voice in voices_with_user_id]
            voice_names2 = [voice.voice_name for voice in voices_without_user_id]
            context ={
                'voice_names1': voice_names1,
                'voice_names2': voice_names2,
                'book_id': book_id,
                'active_tab': 'voice_private'
            }
            return Response(context, template_name=self.template_name)
        except :
            return Response(status=404,template_name=self.template_name)

@method_decorator(login_required(login_url='user:login'), name='dispatch')
class VoiceCelebrityHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/voice_celebrity.html'

    def get(self, request):
        context = {
            'active_tab': 'voice_popular'
        }
        return Response(context, template_name=self.template_name)

class voice_custom_upload(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/voice_custom_upload.html'
    
    def get(self, request):
        book_id = request.GET.get("book_id")

        try:
            context ={
                'book_id': book_id
            }
            return Response(context, template_name=self.template_name)
        except :
            return Response(status=404,template_name=self.template_name)

class voice_custom_complete(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'audiobook/voice_custom_complete.html'
    
    def get(self, request):
        book_id = request.GET.get("book_id")

        try:
            context ={
                'book_id': book_id
            }
            return Response(context, template_name=self.template_name)
        except :
            return Response(status=404,template_name=self.template_name)

def voice_custom_upload_post(request):
    return render(request, 'audiobook/voice_custom.html')

@api_view(['GET'])
def helloAPI(request):
    return Response("hello world!")

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



#중복찾기
class Voice_Custom_Search(View):
    def get(self, request):
        voice_name = request.GET.get('voice_name', None)
        print("i got",voice_name)
        
        if voice_name is None:
            return JsonResponse({'error': 'voice_name parameter is required.'})

        # Voice 모델에서 voice_name 값이 일치하는 객체 찾기
        try:
            voice = Voice.objects.get(voice_name=voice_name)
            print(voice)
            return JsonResponse({'check': 'True'})
        except Voice.DoesNotExist:
            return JsonResponse({'check': 'False'})


class VoiceList(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request):
        faqs = Voice.objects.all()
        serializer = VoiceSerializer(faqs, many=True)
        return Response({"voices": serializer.data})

    def post(self, request):
        serializer = VoiceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'result': True, 'faqs': serializer.data, 'message': 'users created.'})
        return Response({'result': False, 'errors': serializer.errors}, status=400)


class VoiceDetail(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request, pk, format=None):
        voice = get_object_or_404(Voice, pk)
        serializer = VoiceSerializer(voice)
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        voice = get_object_or_404(Voice, pk)
        serializer = VoiceSerializer(voice, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        voice = get_object_or_404(Voice, pk)
        voice.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)