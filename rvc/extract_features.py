import subprocess
import sys

f0method = "rmvpe"
model_name = sys.argv[1]
#%cd /content/drive/MyDrive/project-main
with open(f'./logs/{model_name}/extract_f0_feature.log', 'w') as f:
    f.write("Starting...")

if f0method != "rmvpe_gpu":
    subprocess.run([
        'python',
        './rvc/infer/modules/train/extract/extract_f0_print.py',
        f'./logs/{model_name}',
        '2',
        f'{f0method}'
    ])
else:
    try:
        subprocess.run([
            'python',
            './rvc/infer/modules/train/extract/extract_f0_rmvpe.py',
            '1',
            '0',
            '0',
            f'./logs/{model_name}',
            'True'
        ])
    except:
        print("ERROR")

subprocess.run([
    'python',
    './rvc/infer/modules/train/extract_feature_print.py',
    'cuda:0',
    '1',
    '0',
    '0',
    f'./logs/{model_name}',
    'v2'
])

with open(f'./logs/{model_name}/extract_f0_feature.log', 'r') as f:
    if 'all-feature-done' in f.read():
        print("\u2714 Success")
    else:
        print("Error preprocessing data... Make sure your data was preprocessed.")
