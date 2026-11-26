"""Local timestamped ASR fallback for videos whose captions are unavailable.

Uses faster-whisper on CPU. Media and the model cache stay outside the live
knowledge store. No generated speech is marked expert-reviewed.
"""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_youtube_knowledge as job


def main(args):
    from faster_whisper import WhisperModel
    from yt_dlp import YoutubeDL
    import numpy as np

    manifest = json.loads(job.MANIFEST.read_text(encoding="utf-8"))
    wanted = set(args.ids.split(",")) if args.ids else set()
    records = [r for r in manifest.values() if r["video_id"] in wanted] if wanted else [r for r in manifest.values() if not r.get("chunks")]
    model = None
    audio_dir = job.STAGE / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        vid = record["video_id"]
        raw_path = job.STAGE / "raw" / (vid + ".json")
        if raw_path.exists():
            cached = json.loads(raw_path.read_text(encoding="utf-8"))
            if cached.get("metadata", {}).get("source") == "local_whisper_asr":
                print(f"[audio] {vid}: already transcribed", flush=True)
                continue
        print(f"[audio] {vid}: downloading audio", flush=True)
        with YoutubeDL({"format": "bestaudio/best", "outtmpl": str(audio_dir / "%(id)s.%(ext)s"),
                        "skip_download": False, "quiet": True, "no_warnings": True, "noprogress": True,
                        "js_runtimes": {"node": {}},
                        "socket_timeout": 20, "retries": 2, "extractor_retries": 2}) as downloader:
            information = downloader.extract_info(record["url"], download=True)
            audio_path = Path(downloader.prepare_filename(information))
        if model is None:
            print(f"[audio] loading local ASR model {args.model}", flush=True)
            model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=4,
                                 download_root=str(job.ROOT / "index" / "asr_models"))
        print(f"[audio] {vid}: transcribing", flush=True)
        # Decode through the installed FFmpeg: Dana's PyAV pin predates the
        # metadata_errors keyword used by newer faster-whisper releases.
        audio = np.frombuffer(subprocess.check_output([
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(audio_path),
            "-ar", "16000", "-ac", "1", "-f", "f32le", "pipe:1",
        ]), dtype=np.float32)
        generated, info = model.transcribe(audio, language=None if args.language == "auto" else args.language, beam_size=5,
                                           vad_filter=True, condition_on_previous_text=False,
                                           no_speech_threshold=0.6)
        segments = job.normalize_segments([{"start": s.start, "duration": s.end - s.start, "text": s.text}
                                          for s in generated if s.no_speech_prob < 0.8])
        if not segments:
            record.update(fetch_status="audio_without_speech", source="local_whisper_asr")
            manifest[vid] = record
            job.save_json(job.MANIFEST, manifest)
            print(f"[audio] {vid}: no speech found", flush=True)
            continue
        if any(s["start"] > record["duration_seconds"] + 2 for s in segments):
            raise ValueError("ASR timestamp exceeds actual duration")
        chunks = job.transcript_chunks(segments)
        clean = job.STAGE / "clean" / (vid + ".txt")
        clean.write_text("".join(f"[{start}] {text}\n" for start, text in chunks), encoding="utf-8", newline="\n")
        record.update(fetch_status="audio_transcribed", source="local_whisper_asr", asr_model=args.model,
                      language=info.language, auto_generated=True, visual_review_pending=True,
                      segments=len(segments), chunks=len(chunks),
                      words=sum(len(s["text"].split()) for s in segments),
                      last_caption_second=math.ceil(max(s["start"] + s["duration"] for s in segments)),
                      transcript_sha256=hashlib.sha256(clean.read_bytes()).hexdigest())
        record.pop("error", None)
        record.pop("error_type", None)
        job.save_json(raw_path, {"metadata": record, "segments": segments})
        manifest[vid] = record
        job.save_json(job.MANIFEST, manifest)
        print(f"[audio] {vid}: {len(segments)} segments, {record['words']} words", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default="vi")
    main(parser.parse_args())
