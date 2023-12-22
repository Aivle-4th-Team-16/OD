# 음성파일 preprocessing하는 파일
import os
import subprocess
import sys

#@title 1.Preprocess Data
#%cd /content/drive/MyDrive/project-main
model_name = sys.argv[1] #@param {type:"string"}
#@markdown <small> Enter the path to your dataset folder (a folder with audios of the vocals you will train on), or if you want just upload the audios using the File Manager into the 'dataset' folder.

# 음성파일 저장
dataset_folder = './voices' #@param {type:"string"}
while len(os.listdir(dataset_folder)) < 1:
    input("Your voice folder is empty.")
#!mkdir -p ./logs/{model_name}

log_dir = f"./logs/{model_name}"
os.makedirs(log_dir, exist_ok=True)
print(f"{log_dir} 디렉토리가 생성되었습니다.")
with open(f'./logs/{model_name}/preprocess.log','w') as f:
    print("Starting...")
    
# 명령어와 매개변수 설정
command = [
    "python",
    "rvc/infer/modules/train/preprocess.py",
    dataset_folder,
    "40000",
    "2",
    f"./logs/{model_name}",
    "False",
    "3.0"
]

# 명령어 실행
try:
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, check=True, shell=False)
    print("명령어가 성공적으로 실행되었습니다.")
except subprocess.CalledProcessError as e:
    print(f"명령어 실행 중 오류 발생: {e}")

with open(f'./logs/{model_name}/preprocess.log','r') as f:
    if 'end preprocess' in f.read():
        print("Success")
    else:
        print("Error preprocessing data... Make sure your dataset folder is correct.")