from pathlib import Path
import sys
import time

import torch
import torchaudio
import speech_recognition as sr
from speechbrain.inference.speaker import EncoderClassifier
from speechbrain.utils.fetching import LocalStrategy

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "voice_model_cache"
PROFILE_PATH = BASE_DIR / "nova_voice_profile.pt"
SAMPLE_RATE = 16000
THRESHOLD = 0.35

_classifier = None


def load_classifier():
    global _classifier
    if _classifier is None:
        print("Loading speaker-recognition model...")
        _classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(MODEL_DIR),
            run_opts={"device": "cpu"},
            local_strategy=LocalStrategy.COPY,
        )
    return _classifier


def embedding_from_audio(audio, classifier=None):
    classifier = classifier or load_classifier()
    raw = audio.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2)

    if len(raw) / (SAMPLE_RATE * 2) < 1.0:
        raise ValueError("Recording is too short; speak for at least one second.")

    samples = torch.frombuffer(bytearray(raw), dtype=torch.int16)
    waveform = samples.float().unsqueeze(0) / 32768.0

    with torch.no_grad():
        embedding = classifier.encode_batch(waveform)

    embedding = embedding.reshape(1, -1)
    return torch.nn.functional.normalize(embedding, p=2, dim=1).squeeze(0).cpu()


def enroll():
    if PROFILE_PATH.exists() and "--replace" not in sys.argv:
        raise SystemExit(
            "A voice profile already exists. Use 'enroll --replace' to replace it."
        )

    recognizer = sr.Recognizer()
    classifier = load_classifier()
    embeddings = []

    prompts = [
        "Hey Nova, please listen to my voice.",
        "Nova, open my calculator.",
        "Hey Nova, what can you help me with?",
        "Nova, tell me the time.",
        "Hey Nova, this is my voice profile recording.",
    ]

    print("\nVoice enrolment: record in a quiet room.")
    print("Speak naturally, at your normal volume.")
    with sr.Microphone(sample_rate=SAMPLE_RATE) as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.0)

        for index, prompt in enumerate(prompts, 1):
            print(f"\nRecording {index}/5: {prompt}")
            input("Press Enter, then speak the displayed sentence...")
            audio = recognizer.listen(
                source, timeout=10, phrase_time_limit=7
            )
            embedding = embedding_from_audio(audio, classifier)
            embeddings.append(embedding)
            print("Recording captured.")

    profile_embedding = torch.stack(embeddings).mean(dim=0)
    profile_embedding = torch.nn.functional.normalize(
        profile_embedding, p=2, dim=0
    )

    torch.save(
        {
            "embedding": profile_embedding,
            "threshold": THRESHOLD,
            "version": 1,
        },
        PROFILE_PATH,
    )
    print(f"\nVoice profile saved locally: {PROFILE_PATH}")
    print("Keep this file private; it represents your voice.")


def verify_audio(audio):
    if not PROFILE_PATH.is_file():
        return False, None

    try:
        profile = torch.load(
            PROFILE_PATH, map_location="cpu", weights_only=True
        )
        classifier = load_classifier()
        candidate = embedding_from_audio(audio, classifier)
        reference = profile["embedding"].reshape(1, -1)
        candidate = candidate.reshape(1, -1)

        score = torch.nn.functional.cosine_similarity(
            reference, candidate
        ).item()
        threshold = 0.100
        upper_threshold = 0.500
        if score < 0.20:
            band = "VERY LOW"
        elif score < threshold:
            band = "UNCERTAIN"
        else:
            band = "THRESHOLD PASSED"
        print(f"Voice score: {score:.3f} | {band} | threshold: {threshold:.2f}")
        return threshold <= score <= upper_threshold, score
    except Exception as error:
        print("Speaker verification failed:", error)
        return False, None


def test_verification():
    if not PROFILE_PATH.is_file():
        raise SystemExit("No voice profile found. Run enroll first.")

    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 0.8
    print("Speak a full sentence naturally for 2-4 seconds.")
    print("Start speaking after this message; avoid long pauses.")

    with sr.Microphone(sample_rate=SAMPLE_RATE) as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.0)
        audio = recognizer.listen(
            source, timeout=10, phrase_time_limit=8
        )

    duration = len(audio.get_raw_data()) / (
        audio.sample_rate * audio.sample_width
    )
    print(f"Captured audio duration: {duration:.2f} seconds")

    accepted, score = verify_audio(audio)
    if score is None:
        print("REJECTED: verification unavailable.")
    else:
        print(f"Similarity score: {score:.3f}")
        print("MATCH" if accepted else "REJECTED")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in {"enroll", "test"}:
        raise SystemExit(
            "Usage: python nova_voice_auth.py enroll [--replace]"
            " | test"
        )

    if sys.argv[1] == "enroll":
        enroll()
    else:
        test_verification()


