#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collect.py - channels.txt 기반 유튜브 영상 데이터 수집기

사용법:
    python Collect.py                      # 어제 업로드 영상만 수집
    python Collect.py --date 2026-06-28   # 특정 날짜 영상 수집
    python Collect.py --scan 30           # 날짜 필터링을 위해 채널당 최근 30개까지 스캔
"""

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile

# 콘솔 인코딩을 UTF-8로 강제 설정 (Windows cp949 환경 대응)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from datetime import datetime, timedelta
from pathlib import Path

# ── 설정 ──────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
CHANNELS_FILE = BASE_DIR / "channels.txt"
OUTPUT_DIR    = BASE_DIR / "output"
DEFAULT_SCAN  = 20  # 날짜 필터링을 위해 채널당 스캔할 최대 영상 수

# yt-dlp 경로: PATH에 있으면 자동 사용, 없으면 winget 설치 경로로 폴백
_WINGET_YTDLP = (
    Path.home()
    / "AppData/Local/Microsoft/WinGet/Packages"
    / "yt-dlp.yt-dlp_Microsoft.Winget.Source_8wekyb3d8bbwe"
    / "yt-dlp.exe"
)
YTDLP = "yt-dlp" if shutil.which("yt-dlp") else str(_WINGET_YTDLP)
# ──────────────────────────────────────────────────────────────────────────────


def read_sources() -> list[str]:
    """channels.txt에서 소스 목록 읽기 (주석·빈줄 제외)"""
    with open(CHANNELS_FILE, encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]


def run_ytdlp(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [YTDLP, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def fetch_video_urls(source: str, scan: int) -> list[str]:
    """소스(채널 URL / 검색어)에서 영상 URL 목록 가져오기"""
    result = run_ytdlp(
        "--flat-playlist",
        "--dump-json",
        "--playlist-end", str(scan),
        "--no-warnings",
        "--quiet",
        source,
    )
    if result.returncode != 0 and result.stderr.strip():
        print(f"  [yt-dlp 오류] {result.stderr.strip()[:200]}", file=sys.stderr)
    urls = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            vid_id = entry.get("id", "")
            # id가 URL이 아닌 순수 ID면 직접 조합
            if vid_id and not vid_id.startswith("http"):
                urls.append(f"https://www.youtube.com/watch?v={vid_id}")
            else:
                url = entry.get("url") or entry.get("webpage_url") or ""
                if url:
                    urls.append(url)
        except json.JSONDecodeError:
            pass
    return urls


def clean_vtt(vtt_text: str) -> str:
    """VTT 자막 → 중복 없는 순수 텍스트"""
    seen: set[str] = set()
    lines = []
    for line in vtt_text.splitlines():
        if (
            not line.strip()
            or re.match(r"^\d{2}:\d{2}", line)
            or line.startswith(("WEBVTT", "Kind:", "Language:"))
        ):
            continue
        clean = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", line)
        clean = re.sub(r"</?c>|</?[a-z]+>", "", clean)
        clean = (
            clean.replace("&gt;", ">")
                 .replace("&lt;", "<")
                 .replace("&amp;", "&")
                 .strip()
        )
        if clean and clean not in seen:
            seen.add(clean)
            lines.append(clean)
    return "\n".join(lines)


def fetch_subtitle(video_url: str, tmpdir: str) -> tuple[str | None, str | None]:
    """자막 다운로드 → (언어코드, 텍스트). 한국어 우선, 없으면 영어."""
    run_ytdlp(
        "--skip-download",
        "--write-auto-subs",
        "--write-subs",
        "--sub-langs", "ko,en",
        "--sub-format", "vtt",
        "--no-warnings",
        "--quiet",
        "-o", str(Path(tmpdir) / "%(id)s"),
        video_url,
    )
    m = re.search(r"[?&]v=([A-Za-z0-9_-]+)", video_url)
    vid_id = m.group(1) if m else ""

    for lang in ("ko", "ko-orig", "en"):
        vtt_path = Path(tmpdir) / f"{vid_id}.{lang}.vtt"
        if vtt_path.exists():
            lang_key = "ko" if "ko" in lang else "en"
            return lang_key, clean_vtt(vtt_path.read_text(encoding="utf-8"))
    return None, None


def fetch_video(video_url: str, target_date: str) -> dict | None:
    """단일 영상: 메타데이터 + 자막 수집. target_date(YYYY-MM-DD)와 다르면 None 반환."""
    result = run_ytdlp(
        "--dump-json",
        "--skip-download",
        "--no-warnings",
        "--quiet",
        video_url,
    )
    meta = None
    for line in result.stdout.splitlines():
        if line.strip().startswith("{"):
            try:
                meta = json.loads(line)
                break
            except json.JSONDecodeError:
                pass
    if not meta:
        print(f"  [오류] 메타데이터 없음: {video_url}", file=sys.stderr)
        return None

    raw_date = meta.get("upload_date", "")
    upload_date = (
        f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        if len(raw_date) == 8 else raw_date
    )

    # 날짜 필터: 대상 날짜와 다르면 스킵
    if upload_date != target_date:
        print(f"  [스킵] 업로드일 {upload_date} (대상: {target_date})")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        sub_lang, subtitle = fetch_subtitle(video_url, tmpdir)

    return {
        "title":         meta.get("title"),
        "channel":       meta.get("channel") or meta.get("uploader"),
        "view_count":    meta.get("view_count"),
        "upload_date":   upload_date,
        "url":           meta.get("webpage_url") or video_url,
        "subtitle_lang": sub_lang,
        "subtitle":      subtitle,
    }


def main():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(description="유튜브 영상 데이터 수집기 (날짜 필터)")
    parser.add_argument(
        "--date", default=yesterday, metavar="YYYY-MM-DD",
        help=f"수집할 업로드 날짜 (기본값: 어제 {yesterday})",
    )
    parser.add_argument(
        "--scan", type=int, default=DEFAULT_SCAN, metavar="N",
        help=f"채널당 날짜 필터용 스캔 영상 수 (기본값: {DEFAULT_SCAN})",
    )
    args = parser.parse_args()
    target_date = args.date

    # 출력 폴더: output/YYYY-MM-DD/
    date_dir = OUTPUT_DIR / target_date
    date_dir.mkdir(parents=True, exist_ok=True)

    sources = read_sources()
    if not sources:
        print("channels.txt에 수집할 소스가 없습니다.")
        return

    print(f"수집 날짜: {target_date}")
    print(f"소스: {len(sources)}개, 채널당 최근 {args.scan}개 스캔\n")

    all_results: dict = {
        "target_date":  target_date,
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "sources": [],
    }
    total_videos = 0

    for source in sources:
        print(f"[스캔] {source}")
        video_urls = fetch_video_urls(source, args.scan)
        print(f"  → {len(video_urls)}개 발견, 날짜 필터 적용 중...")

        source_entry: dict = {"source": source, "videos": []}
        for i, url in enumerate(video_urls, 1):
            print(f"  [{i}/{len(video_urls)}] {url}")
            video = fetch_video(url, target_date)
            if video:
                source_entry["videos"].append(video)
                total_videos += 1

        if not source_entry["videos"]:
            print(f"  → {target_date} 업로드 영상 없음, 스킵\n")
            continue

        print(f"  → {len(source_entry['videos'])}개 수집 완료\n")
        all_results["sources"].append(source_entry)

    ts = datetime.now().strftime("%H%M%S")
    out_path = date_dir / f"collected_{ts}.json"
    out_path.write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if total_videos == 0:
        print(f"\n{target_date}에 업로드된 영상이 없습니다. (기록 저장: {out_path})")
    else:
        print(f"완료 - 총 {total_videos}개 영상 → {out_path}")


if __name__ == "__main__":
    main()
