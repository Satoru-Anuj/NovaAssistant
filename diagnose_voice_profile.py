from pathlib import Path
import torch
import torch.nn.functional as F
import nova_voice_auth as auth

profile_path = auth.PROFILE_PATH
profile = torch.load(
    profile_path, map_location="cpu", weights_only=True
)
reference = F.normalize(
    profile["embedding"].float().reshape(1, -1), dim=1
)

print("Profile shape:", tuple(reference.shape))
print("Saved threshold:", profile.get("threshold"))
print("Reference norm:", reference.norm().item())
print("\nNo original enrollment recordings are saved by the current code.")
print("Therefore, the five original enrollment embeddings cannot be")
print("reconstructed from this profile alone.")
print("\nNext diagnostic: test multiple fresh recordings and compare scores.")
