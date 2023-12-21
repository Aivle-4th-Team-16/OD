import subprocess
from django.shortcuts import render

def index(request):
    if request.method == 'POST':
        text = request.POST.get('my_textarea')
        subprocess.run(['python', 'project-main/preprocess.py', text])
        return render(request, 'rvc_test/index.html', {'text': text})
    else:
        return render(request, 'rvc_test/index.html')
