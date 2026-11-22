"""렌더링된 시안(이미지·영상)을 인스타(카드뉴스·릴스)·스레드·유튜브 쇼츠에 직접 올린다 (각 서비스 API 토큰 사용).

네이버 블로그·클립은 여기서 올리지 않는다. Uplika를 쓰는 루틴 ②가 published.json 의 영상·이미지 주소를 받아 올린다.
LLM(API)은 쓰지 않는다.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .bgm import with_credit
from .config import Settings
from .frames import blog_images_of, capture_frames, frames_of, make_blog_images
from .hosting import make_host
from .llm import CardNews, TopicIdea
from .publishers import make_publishers

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))


def caption_hashtags(caption: str) -> list[str]:
    """인스타 캡션에서 해시태그를 순서대로, 중복 없이 뽑는다."""
    tags: list[str] = []
    for t in re.findall(r"#[^\s#]+", caption):
        if t not in tags:
            tags.append(t)
    return tags


def _meta(folder: Path) -> dict:
    p = folder / "published.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def is_done(folder: Path, platforms: list[str]) -> bool:
    return all(p in _meta(folder).get("posts", {}) for p in platforms)


def latest_unpublished(root: Path, s: Settings, now: datetime | None = None, max_age_days: int = 1) -> Path | None:
    """가장 최근에 렌더링된 폴더 중 아직 다 안 올린 것. 너무 오래된 폴더(날짜 기준)는 늦게 올리지 않는다."""
    today = (now or datetime.now(KST)).astimezone(KST).date()
    for d in sorted((x for x in root.iterdir() if x.is_dir()), reverse=True) if root.exists() else []:
        if not (d / "reel.mp4").exists() or not (d / "slide_01.jpg").exists():
            continue
        try:
            made = datetime.strptime(d.name[:8], "%Y%m%d").date()
        except ValueError:
            continue
        if (today - made).days > max_age_days:
            return None  # 최신 폴더가 이미 오래됐다면 그보다 옛것은 볼 필요 없다
        if not is_done(d, s.platforms):
            return d
        return None  # 최신 폴더는 이미 다 올렸다
    return None


def publish_folder(folder: Path, s: Settings, dry_run: bool = False, host=None, publishers=None) -> dict:
    CardNews.model_validate_json((folder / "card.json").read_text(encoding="utf-8"))
    topic = TopicIdea.model_validate_json((folder / "topic.json").read_text(encoding="utf-8"))
    caption = (folder / "caption.txt").read_text(encoding="utf-8").strip()
    threads_text = (folder / "threads.txt").read_text(encoding="utf-8").strip()[:500]
    # CC BY 곡의 출처 표기는 영상이 올라가는 곳(인스타 릴스·유튜브)의 설명에만 붙인다. 스레드에는 붙이지 않는다.
    caption = with_credit(caption, folder, 2200)
    reel = folder / "reel.mp4"
    # 이미지 두 벌: 네이버 블로그(루틴 ②)는 정사각형(blog_NN.jpg), 스레드 캐러셀은 릴스 영상 캡처(세로 frame_NN.jpg).
    # 네이버 피드 썸네일이 정사각형이라 세로 그림을 그대로 올리면 위아래가 잘린다. 영상이 없으면 슬라이드를 쓴다.
    reel_frames = frames_of(folder)
    if not reel_frames and reel.exists() and not dry_run:
        try:
            reel_frames = capture_frames(folder)
        except Exception as e:
            log.warning("릴스 장면 캡처 실패, 슬라이드를 대신 씁니다: %s", e)
    squares = blog_images_of(folder)
    if not squares and not dry_run:
        try:
            squares = make_blog_images(folder)
        except Exception as e:
            log.warning("블로그용 정사각형 이미지 만들기 실패, 슬라이드를 대신 씁니다: %s", e)
    images = squares or sorted(folder.glob("slide_*.jpg"))

    if dry_run:
        pubs = publishers if publishers is not None else make_publishers(s)
        plan = {"folder": folder.name, "platforms": [p.name for p in pubs], "images": len(images), "reel": reel.exists(),
                "caption_chars": len(caption), "threads_chars": len(threads_text), "title": topic.title,
                "already": sorted(_meta(folder).get("posts", {}))}
        log.info("(시험 실행, 실제로 올리지 않음) %s", json.dumps(plan, ensure_ascii=False))
        return plan

    meta = _meta(folder)
    meta_path = folder / "published.json"
    save = lambda: meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")  # noqa: E731

    def stale(urls: list[str], files: list[Path]) -> bool:  # 비ASCII URL은 Meta가 못 가져오고, 파일이 바뀌었으면 다시 올린다
        return not urls or not all(u.isascii() for u in urls) or [u.rsplit("/", 1)[-1] for u in urls] != [p.name for p in files]

    if stale(meta.get("image_urls") or [], images):
        host = host or make_host(s)
        meta["image_urls"] = host.upload(images, folder.name)
        save()
    pubs = publishers if publishers is not None else make_publishers(s)
    pending = [p for p in pubs if p.name not in meta.get("posts", {})]
    if any(p.name == "threads" for p in pending) and len(reel_frames) >= 2 and stale(meta.get("threads_image_urls") or [], reel_frames):
        host = host or make_host(s)
        meta["threads_image_urls"] = host.upload(reel_frames, folder.name)
        save()
    if any(getattr(p, "needs_video", False) for p in pending) and not meta.get("video_urls") and reel.exists():
        host = host or make_host(s)
        video_url, cover_url = host.upload([reel, folder / "reel_cover.jpg"], folder.name)
        meta["video_urls"] = host.candidates(video_url)
        meta["reel_cover_url"] = cover_url
        save()
    # 인스타 카드 슬라이드(캐러셀)를 다시 켠 경우에만 슬라이드 원본도 올린다 (캡처는 세로 9:16이라 캐러셀 비율이 안 맞는다)
    if (any(p.name == "instagram" for p in pending) and images and not images[0].name.startswith("slide_")
            and not meta.get("slide_urls")):
        host = host or make_host(s)
        meta["slide_urls"] = host.upload(sorted(folder.glob("slide_*.jpg")), folder.name)
        save()
    assets = {k: meta.get(k) for k in ("image_urls", "threads_image_urls", "slide_urls", "video_urls", "reel_cover_url")}
    assets["video_path"] = str(reel) if reel.exists() else None  # 유튜브는 파일을 직접 올린다
    assets["title"] = topic.title
    assets["hashtags"] = caption_hashtags(caption)

    failures = []
    for pub in pubs:
        if pub.name in meta.get("posts", {}):
            log.info("%s: 이미 게시됨, 건너뜀", pub.name)
            continue
        text = threads_text if pub.name == "threads" else caption
        try:
            res = pub.publish(assets, text)
        except Exception as e:
            log.error("%s 게시 실패: %s", pub.name, e)
            meta.setdefault("errors", {})[pub.name] = str(e)
            failures.append(f"{pub.name}: {e}")
            save()
            continue
        log.info("%s 게시 완료: %s", pub.name, res.permalink or res.media_id)
        meta.setdefault("posts", {})[pub.name] = {"media_id": res.media_id, "permalink": res.permalink}
        meta.get("errors", {}).pop(pub.name, None)
        save()
    meta["failures"] = failures
    save()
    return meta


def check_credentials(s: Settings, publishers=None) -> dict[str, str]:
    """토큰이 실제로 통하는지 읽기 전용 호출로만 확인한다 (아무것도 올리지 않는다). {플랫폼: 결과 문장}"""
    out: dict[str, str] = {}
    pubs = publishers if publishers is not None else make_publishers(s)
    seen = set()
    for p in pubs:
        key = p.name if p.name != "reels" else "instagram"  # 릴스와 인스타는 같은 계정이라 한 번만
        if key in seen:
            continue
        seen.add(key)
        try:
            if p.name in ("instagram", "reels", "threads"):
                me = p.api.get(p.user_id, fields="username")
                out[key] = f"정상 (계정 @{me.get('username', '?')})"
            elif p.name == "youtube":
                cid, title = p.my_channel()
                want = getattr(p, "channel_id", "")
                out[key] = f"정상 (채널 {title}, {cid})" + ("" if not want or want == cid else f" — 경고: YOUTUBE_CHANNEL_ID({want})와 다른 채널입니다")
            else:
                out[key] = "확인 방법 없음"
        except Exception as e:  # 토큰 값이 로그에 남지 않게 메시지만 짧게
            out[key] = f"실패: {str(e)[:200]}"
    return out
