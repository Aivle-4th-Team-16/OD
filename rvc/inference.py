import subprocess

transpose = 0
input_path = "audios/someguy.mp3"
index_path = "logs/test/trained_IVF7_Flat_nprobe_1_test2_v2.index"
f0_method = "rmvpe"
opt_path = "audios/cli_output.wav"
model_name = "test.pth"
index_rate = 0.66
volume_normalization = 0
consonant_protection = 0

command = [
    "python",
    "rvc/tools/infer_cli.py",
    "--f0up_key", str(transpose),
    "--input_path", input_path,
    "--index_path", index_path,
    "--f0method", f0_method,
    "--opt_path", opt_path,
    "--model_name", model_name,
    "--index_rate", str(index_rate),
    "--device", "cpu",
    "--is_half", "True",
    "--filter_radius", "3",
    "--resample_sr", "0",
    "--rms_mix_rate", str(volume_normalization),
    "--protect", str(consonant_protection)
]

try:
    subprocess.run(command, check=True)
    print("Inference completed successfully.")
except subprocess.CalledProcessError as e:
    print(f"Error during inference: {e}")

