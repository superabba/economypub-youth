"""content/<폴더>/ 의 원고 JSON을 읽어 카드 이미지와 릴스 영상을 만든다. LLM(API) 호출은 없다.

입력(content/<날짜-주제>/):
  topic.json  주제 (TopicIdea)        card.json  슬라이드·캡션·해시태그·스레드 글 (CardNews)
  reel.json   릴스 연출 (style, reason, lines[{slide,text}], card_mid, card_last)   blog.md  네이버 블로그 글
출력(out/<날짜-주제>/): slide_XX.jpg, reel.mp4, reel_cover.jpg, music.json, reel_plan.json, caption.txt, threads.txt, blog.md
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

from . import lemoreel
from .config import ROOT
from .llm import CardNews, TopicIdea, instagram_caption, normalize
from .render import render_card

log = logging.getLogger(__name__)

CONTENT_ROOT = ROOT.parent / "content"
OUT_ROOT = ROOT.parent / "out"


class FixedWriter:
    """LLM 대신 reel.json에 써 둔 연출·내레이션을 돌려주는 작가. lemoreel.plan_reel이 부르는 _parse만 흉내 낸다."""

    def __init__(self, plan: lemoreel.ReelPlan):
        self.plan = plan

    def _parse(self, system: str, user: str, schema):
        if schema is lemoreel.ReelPlan:
            return self.plan
        raise RuntimeError(f"이 저장소에는 LLM이 없습니다 (요청한 형식: {getattr(schema, '__name__', schema)})")


def load(folder: Path) -> tuple[TopicIdea, CardNews, lemoreel.ReelPlan]:
    topic = TopicIdea.model_validate_json((folder / "topic.json").read_text(encoding="utf-8"))
    card = normalize(CardNews.model_validate_json((folder / "card.json").read_text(encoding="utf-8")), 5, 9)
    raw = json.loads((folder / "reel.json").read_text(encoding="utf-8"))
    plan = lemoreel.ReelPlan(
        style=raw["style"], reason=raw.get("reason", ""), card_mid=raw.get("card_mid", ""), card_last=raw.get("card_last", ""),
        lines=[lemoreel.NarrationLine(slide=int(x["slide"]), text=str(x["text"])) for x in raw["lines"]],
    )
    return topic, card, plan


def render_folder(src: Path, out_root: Path = OUT_ROOT) -> Path:
    topic, card, plan = load(src)
    out = out_root / src.name
    out.mkdir(parents=True, exist_ok=True)
    for name in ("topic.json", "card.json", "reel.json", "blog.md"):
        if (src / name).exists():
            shutil.copy2(src / name, out / name)
    fonts_dir = ROOT / "fonts"
    handle = os.environ.get("BRAND_HANDLE") or "@economypub"
    theme = os.environ.get("CARD_THEME") or "midnight"
    log.info("카드 이미지: %s", src.name)
    render_card(card, out, fonts_dir, theme, handle)
    (out / "caption.txt").write_text(instagram_caption(card), encoding="utf-8")
    (out / "threads.txt").write_text(card.threads_text, encoding="utf-8")
    log.info("릴스 영상 (스타일 %s)", plan.style)
    lemoreel.make_reel(
        card, topic, out, FixedWriter(plan), fonts_dir, handle, style=plan.style,
        voice=os.environ.get("REELS_VOICE") or lemoreel.DEFAULT_VOICE,
        rate=os.environ.get("REELS_VOICE_RATE") or "+0%", fps=int(os.environ.get("REELS_FPS") or 30),
    )
    return out


def pending(content_root: Path = CONTENT_ROOT, out_root: Path = OUT_ROOT) -> list[Path]:
    """원고는 있는데 아직 영상이 없는 폴더."""
    if not content_root.exists():
        return []
    return [d for d in sorted(content_root.iterdir())
            if d.is_dir() and (d / "card.json").exists() and not (out_root / d.name / "reel.mp4").exists()]
