
import json
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "Nova_Exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm",
    ".m4v", ".wmv", ".flv"
}


def find_ffmpeg():
    """Return the FFmpeg executable path or None."""
    return shutil.which("ffmpeg")


def find_ffprobe():
    """Return the FFprobe executable path or None."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return None

    candidate = Path(ffmpeg).with_name("ffprobe.exe")
    if candidate.is_file():
        return str(candidate)

    return shutil.which("ffprobe")


def validate_video(path):
    """Validate that the selected video file exists."""
    file_path = Path(path).expanduser().resolve()

    if not file_path.is_file():
        raise FileNotFoundError(f"Video file not found: {file_path}")

    if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("That file extension is not supported.")

    return file_path


def probe_video(path):
    """Read video metadata using FFprobe."""
    file_path = validate_video(path)
    ffprobe = find_ffprobe()

    if not ffprobe:
        raise RuntimeError("FFprobe was not found.")

    result = subprocess.run(
        [
            ffprobe, "-v", "error",
            "-show_format", "-show_streams",
            "-of", "json", str(file_path)
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True
    )

    return json.loads(result.stdout)


def run_ffmpeg(arguments, timeout=3600):
    """Run FFmpeg and return a readable result."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg is not installed or not on PATH.")

    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-y", *map(str, arguments)],
        capture_output=True,
        text=True,
        timeout=timeout
    )

    if result.returncode != 0:
        details = (result.stderr or "Unknown FFmpeg error")[-1800:]
        raise RuntimeError(details)

    return "Export completed successfully."


def output_path(source, suffix):
    """Create a unique export name without replacing existing files."""
    source = validate_video(source)
    destination = EXPORT_DIR / f"{source.stem}_{suffix}{source.suffix}"
    counter = 2

    while destination.exists():
        destination = EXPORT_DIR / f"{source.stem}_{suffix}_{counter}{source.suffix}"
        counter += 1

    return destination


def trim_video(source, start_seconds, duration_seconds):
    """Export a segment using seconds."""
    source = validate_video(source)
    start = float(start_seconds)
    duration = float(duration_seconds)

    if start < 0 or duration <= 0:
        raise ValueError("Start must be non-negative and duration must be positive.")

    destination = output_path(source, "trimmed")

    run_ffmpeg([
        "-ss", str(start),
        "-i", str(source),
        "-t", str(duration),
        "-map", "0:v:0",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(destination)
    ])

    return f"Trimmed video saved to: {destination}"


def extract_audio(source):
    """Extract audio from a video into an M4A file."""
    source = validate_video(source)
    destination = EXPORT_DIR / f"{source.stem}_audio.m4a"
    counter = 2

    while destination.exists():
        destination = EXPORT_DIR / f"{source.stem}_audio_{counter}.m4a"
        counter += 1

    run_ffmpeg([
        "-i", str(source),
        "-vn",
        "-c:a", "aac",
        "-b:a", "192k",
        str(destination)
    ])

    return f"Audio saved to: {destination}"


def change_speed(source, speed):
    """Change video and audio speed together."""
    source = validate_video(source)
    speed = float(speed)

    if not 0.25 <= speed <= 4.0:
        raise ValueError("Speed must be between 0.25x and 4x.")

    destination = output_path(source, "speed")
    video_filter = f"setpts=PTS/{speed:g}"
    audio_filter = f"atempo={speed:g}"

    run_ffmpeg([
        "-i", str(source),
        "-vf", video_filter,
        "-af", audio_filter,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(destination)
    ])

    return f"Speed-adjusted video saved to: {destination}"


def crop_video(source, width, height, x=0, y=0):
    """Crop a video to the requested dimensions."""
    source = validate_video(source)
    width, height, x, y = map(int, (width, height, x, y))

    if min(width, height) <= 0 or min(x, y) < 0:
        raise ValueError("Crop dimensions must be positive and offsets non-negative.")

    destination = output_path(source, "cropped")

    run_ffmpeg([
        "-i", str(source),
        "-vf", f"crop={width}:{height}:{x}:{y}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-movflags", "+faststart",
        str(destination)
    ])

    return f"Cropped video saved to: {destination}"


def resize_video(source, width, height):
    """Resize video while preserving a valid even output size."""
    source = validate_video(source)
    width, height = int(width), int(height)

    if not (2 <= width <= 7680 and 2 <= height <= 4320):
        raise ValueError("Choose dimensions between 2x2 and 7680x4320.")

    width -= width % 2
    height -= height % 2
    destination = output_path(source, "resized")

    run_ffmpeg([
        "-i", str(source),
        "-vf", f"scale={width}:{height}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-movflags", "+faststart",
        str(destination)
    ])

    return f"Resized video saved to: {destination}"


def convert_to_mp4(source):
    """Convert a supported video to MP4."""
    source = validate_video(source)
    destination = EXPORT_DIR / f"{source.stem}_converted.mp4"
    counter = 2

    while destination.exists():
        destination = EXPORT_DIR / f"{source.stem}_converted_{counter}.mp4"
        counter += 1

    run_ffmpeg([
        "-i", str(source),
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-movflags", "+faststart",
        str(destination)
    ])

    return f"MP4 saved to: {destination}"

def adjust_brightness(source, brightness):
    """Adjust brightness from -1.0 to 1.0."""
    source = validate_video(source)
    brightness = float(brightness)

    if not -1.0 <= brightness <= 1.0:
        raise ValueError("Brightness must be between -1.0 and 1.0.")

    destination = output_path(source, "brightness")

    run_ffmpeg([
        "-i", str(source),
        "-vf", f"eq=brightness={brightness:g}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-movflags", "+faststart",
        str(destination)
    ])

    return f"Brightness-adjusted video saved to: {destination}"


def adjust_volume(source, volume):
    """Adjust audio volume from 0x to 5x."""
    source = validate_video(source)
    volume = float(volume)

    if not 0.0 <= volume <= 5.0:
        raise ValueError("Volume must be between 0x and 5x.")

    destination = output_path(source, "volume")

    run_ffmpeg([
        "-i", str(source),
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "copy",
        "-af", f"volume={volume:g}",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(destination)
    ])

    return f"Volume-adjusted video saved to: {destination}"


def handle_voice_command(command):
    """Handle explicit Nova video-editing commands; return None otherwise."""
    import tkinter as tk
    from tkinter import filedialog, simpledialog

    text = str(command).lower().strip()
    triggers = (
        "edit video", "trim video", "trim the video",
        "extract audio", "video audio", "change video speed",
        "speed up video", "slow down video", "crop video",
        "resize video", "convert video to mp4",
        "convert to mp4", "brighten video", "video brightness",
        "adjust video volume", "video volume",
        "mute video"
    )

    if not any(phrase in text for phrase in triggers):
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        source = filedialog.askopenfilename(
            title="Choose a video to edit",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.wmv *.flv"),
                ("All files", "*.*")
            ]
        )

        if not source:
            return "Video editing cancelled."

        if "extract audio" in text or "video audio" in text:
            return extract_audio(source)

        if "trim" in text:
            start = simpledialog.askfloat(
                "Trim video", "Start time in seconds:", minvalue=0, parent=root
            )
            if start is None:
                return "Trimming cancelled."

            duration = simpledialog.askfloat(
                "Trim video", "Duration in seconds:", minvalue=0.01, parent=root
            )
            if duration is None:
                return "Trimming cancelled."

            return trim_video(source, start, duration)

        if "speed" in text or "slow down video" in text:
            speed = simpledialog.askfloat(
                "Video speed",
                "Speed multiplier (0.25 to 4; e.g. 2 = twice as fast):",
                minvalue=0.25, maxvalue=4.0, parent=root
            )
            if speed is None:
                return "Speed adjustment cancelled."
            return change_speed(source, speed)

        if "crop video" in text:
            width = simpledialog.askinteger(
                "Crop video", "Crop width in pixels:", minvalue=2, parent=root
            )
            if width is None:
                return "Cropping cancelled."

            height = simpledialog.askinteger(
                "Crop video", "Crop height in pixels:", minvalue=2, parent=root
            )
            if height is None:
                return "Cropping cancelled."

            x = simpledialog.askinteger(
                "Crop video", "Horizontal offset (x):", minvalue=0,
                initialvalue=0, parent=root
            )
            if x is None:
                return "Cropping cancelled."

            y = simpledialog.askinteger(
                "Crop video", "Vertical offset (y):", minvalue=0,
                initialvalue=0, parent=root
            )
            if y is None:
                return "Cropping cancelled."

            return crop_video(source, width, height, x, y)

        if "resize video" in text:
            width = simpledialog.askinteger(
                "Resize video", "Output width in pixels:",
                minvalue=2, maxvalue=7680, parent=root
            )
            if width is None:
                return "Resizing cancelled."

            height = simpledialog.askinteger(
                "Resize video", "Output height in pixels:",
                minvalue=2, maxvalue=4320, parent=root
            )
            if height is None:
                return "Resizing cancelled."

            return resize_video(source, width, height)

        if "convert" in text:
            return convert_to_mp4(source)

        if "brighten video" in text or "video brightness" in text:
            brightness = simpledialog.askfloat(
                "Brightness",
                "Brightness (-1 = darker, 0 = unchanged, 1 = brighter):",
                minvalue=-1.0, maxvalue=1.0, parent=root
            )
            if brightness is None:
                return "Brightness adjustment cancelled."
            return adjust_brightness(source, brightness)

        if "volume" in text or "mute video" in text:
            volume = 0.0 if "mute video" in text else simpledialog.askfloat(
                "Video volume", "Volume multiplier (0 = mute, 1 = original, 2 = double):",
                minvalue=0.0, maxvalue=5.0, parent=root
            )
            if volume is None:
                return "Volume adjustment cancelled."
            return adjust_volume(source, volume)

        return "Say a specific video-editing command, such as trim video or convert to MP4."

    except Exception as error:
        return f"Video editing failed: {error}"

    finally:
        root.destroy()

# NOVA_STUDIO_ENGINE_UPGRADE_V1

def adjust_color(source, contrast=1.0, saturation=1.0):
    """Adjust contrast (0-3) and saturation (0-3), preserving audio."""
    source = validate_video(source)
    contrast = float(contrast)
    saturation = float(saturation)

    if not 0.0 <= contrast <= 3.0:
        raise ValueError("Contrast must be between 0 and 3.")
    if not 0.0 <= saturation <= 3.0:
        raise ValueError("Saturation must be between 0 and 3.")

    destination = output_path(source, "color")
    run_ffmpeg([
        "-i", str(source),
        "-vf", f"eq=contrast={contrast:g}:saturation={saturation:g}",
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(destination)
    ])
    return f"Color-adjusted video saved to: {destination}"


def normalize_audio(source):
    """Normalize audio loudness using FFmpeg's loudness filter."""
    source = validate_video(source)
    destination = output_path(source, "normalized_audio")
    run_ffmpeg([
        "-i", str(source),
        "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "copy",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(destination)
    ])
    return f"Audio-normalized video saved to: {destination}"


def trim_segments(source, segments):
    """Export each (start_seconds, end_seconds) range as a separate clip."""
    source = validate_video(source)
    if not isinstance(segments, (list, tuple)) or not segments:
        raise ValueError("Provide at least one (start, end) time range.")

    results = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, (list, tuple)) or len(segment) != 2:
            raise ValueError("Each segment must contain a start and end time.")

        start, end = map(float, segment)
        if start < 0 or end <= start:
            raise ValueError("Each end time must be greater than its start time.")

        destination = output_path(source, f"segment_{index}")
        run_ffmpeg([
            "-ss", str(start), "-i", str(source),
            "-t", str(end - start),
            "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(destination)
        ])
        results.append(str(destination))

    return "Exported clips:\n" + "\n".join(results)
