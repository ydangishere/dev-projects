"""Transcribe videos without public captions, using the existing Gemini key.

Keeps speech and visual observations separate in the raw record. Observations
included in retrieval text are explicitly labelled as unreviewed AI descriptions.
"""
import argparse
import concurrent.futures
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_youtube_knowledge as job

PROMPT = """Xem và nghe trực tiếp toàn bộ video này. Không dùng kiến thức bên ngoài.
Chép NGUYÊN VĂN lời nói nghe được, giữ mốc giây và không tự sáng tác lời nói.
Nếu chỉ có nhạc, speech_present=false và segments là danh sách rỗng.
Với hình ảnh, mô tả riêng những chi tiết kỹ thuật thực sự nhìn rõ, không đoán
thông số, mã phụ tùng, cách đấu điện hoặc nguyên nhân hỏng chỉ dựa vào hình.
Trả một JSON object với các trường:
speech_present: boolean;
segments: danh sách object gồm start (giây), duration (giây), text (nguyên văn lời nói);
visual_notes: danh sách object gồm t (giây), text (điều nhìn rõ);
technical_content: boolean (liên quan xe, cơ khí, điện, gia công hoặc dụng cụ);
summary: tóm tắt chính xác nội dung toàn bộ video;
uncertainties: danh sách điểm nghe/nhìn không rõ.
Không coi quảng cáo hay du lịch/ca nhạc tự thân là kiến thức sửa xe.
"""


def transcribe(record, model):
    import gemini_client  # Loads the existing local .env, without printing it.
    from google import genai
    from google.genai import types

    vid = record["video_id"]
    destination = job.STAGE / "video_observations" / (vid + ".json")
    if destination.exists():
        result = json.loads(destination.read_text(encoding="utf-8"))
    else:
        client = genai.Client(http_options=types.HttpOptions(timeout=120000, retry_options=types.HttpRetryOptions(attempts=1)))
        try:
            response = client.models.generate_content(
                model=model,
                contents=[types.Part.from_uri(file_uri=record["url"], mime_type="video/mp4"),
                          f"Video: {record['title']}. Thời lượng thực tế: {record['duration_seconds']} giây. "
                          "Mọi mốc start phải nằm trong thời lượng thực tế; duration là độ dài đoạn, không phải mốc kết thúc.\n" + PROMPT],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0,
                                                  max_output_tokens=16000))
            result = json.loads(response.text or "")
            result.update(video_id=vid, model=model, observed_at_utc=job.now(),
                          source="gemini_youtube_video", expert_reviewed=False,
                          usage=response.usage_metadata.model_dump(mode="json") if response.usage_metadata else {})
            job.save_json(destination, result)
        finally:
            client.close()
    duration = record["duration_seconds"]
    if not result.get("technical_content"):
        record.update(fetch_status="nontechnical_video_reviewed", video_summary=result.get("summary", ""),
                      source="gemini_youtube_video", visual_review_pending=True)
        return record
    segments = job.normalize_segments(result.get("segments", []))
    if any(s["start"] > duration + 2 for s in segments):
        raise ValueError("Generated speech timestamp exceeds video duration")
    observations = result.get("visual_notes", [])
    if result.get("technical_content") and not segments:
        segments = [{"start": float(note["t"]), "duration": 1,
                     "text": "Thông tin hình ảnh (AI mô tả, chưa được thợ duyệt): " + note["text"]}
                    for note in observations if 0 <= float(note["t"]) <= duration]
        if not segments:
            raise ValueError("Technical video has no usable speech or visual observations")
    if not segments:
        raise ValueError("No usable video content returned")
    job.save_json(job.STAGE / "raw" / (vid + ".json"),
                  {"metadata": dict(record, source="gemini_youtube_video", auto_generated=True,
                                    visual_review_pending=True), "segments": segments})
    chunks = job.transcript_chunks(segments)
    clean = job.STAGE / "clean" / (vid + ".txt")
    clean.parent.mkdir(parents=True, exist_ok=True)
    clean.write_text("".join(f"[{start}] {text}\n" for start, text in chunks), encoding="utf-8", newline="\n")
    record.update(fetch_status="video_transcribed", source="gemini_youtube_video", language="vi",
                  auto_generated=True, visual_review_pending=True, segments=len(segments), chunks=len(chunks),
                  words=sum(len(s["text"].split()) for s in segments),
                  last_caption_second=math.ceil(max(s["start"] + s["duration"] for s in segments)),
                  transcript_sha256=hashlib.sha256(clean.read_bytes()).hexdigest())
    record.pop("error", None)
    record.pop("error_type", None)
    return record


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    manifest = json.loads(job.MANIFEST.read_text(encoding="utf-8"))
    pending = [r for r in manifest.values() if not r.get("chunks") and r.get("fetch_status") != "nontechnical_video_reviewed"]
    if args.limit:
        pending = pending[:args.limit]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(transcribe, r, args.model): r for r in pending}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            record = futures[future]
            try:
                result = future.result()
                manifest[record["video_id"]] = result
                job.save_json(job.MANIFEST, manifest)
                print(f"[video {index}/{len(pending)}] {record['video_id']}: {result['fetch_status']}", flush=True)
            except Exception as exc:
                print(f"[video {index}/{len(pending)}] {record['video_id']}: {type(exc).__name__}: {str(exc)[:400]}", flush=True)
