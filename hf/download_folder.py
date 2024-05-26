from huggingface_hub import snapshot_download

# Define the model IDs and the corresponding directories
model_ids = [
    "google/paligemma-3b-mix-224",
    "google/paligemma-3b-mix-448",
    "google/paligemma-3b-pt-224",
    "google/paligemma-3b-pt-448",
    "google/paligemma-3b-pt-896"
]

base_dir = "/pond/modelZoo/vlm/paligemma"

# Hugging Face token
token = "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"

# Download each model to its respective subdirectory
for model_id in model_ids:
    print(f"Downloading {model_id}...")
    subdir = f"{base_dir}/{model_id.split('/')[-1]}"
    snapshot_download(repo_id=model_id, cache_dir=subdir, use_auth_token=token)

print("Models downloaded successfully.")
