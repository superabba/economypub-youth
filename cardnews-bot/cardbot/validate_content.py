"""원고 폴더를 올리기 전에 형식을 확인한다. pydantic만 있으면 돌아간다 (루틴이 밀어 넣기 전에 실행).

사용: python -m cardbot.validate_content content/<날짜-주제>
형식이 틀리면 이유를 한국어로 모두 출력하고 종료 코드 1을 돌려준다.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .llm import CardNews, TopicIdea

STYLES = ("caption-news", "chalkboard", "swiss-motion", "news-package", "whiteboard", "blueprint", "halftone-dossier", "transit-map")  # 비트 스타일은 컷 구성이 달라 이 저장소에서는 쓰지 않는다
RECENT = 2  # 직전 두 편과 같은 스타일은 쓰지 않는다


def _previous(folder: Path, n: int) -> list[Path]:
    sibs = sorted(d for d in folder.parent.iterdir() if d.is_dir() and d.name < folder.name and (d / "reel.json").exists())
    return sibs[-n:]


def check(folder: Path) -> list[str]:
    errs: list[str] = []
    for name in ("topic.json", "card.json", "reel.json", "blog.md"):
        if not (folder / name).exists():
            errs.append(f"{name} 파일이 없습니다")
    if errs:
        return errs
    try:
        topic = TopicIdea.model_validate_json((folder / "topic.json").read_text(encoding="utf-8"))
        card = CardNews.model_validate_json((folder / "card.json").read_text(encoding="utf-8"))
    except Exception as e:  # pydantic 오류 메시지를 그대로 보여 준다
        return [f"topic.json/card.json 형식 오류: {e}"]
    n = len(card.slides)
    if not 5 <= n <= 9:
        errs.append(f"슬라이드는 5~9장이어야 합니다 (지금 {n}장)")
    if card.slides[0].kind != "cover":
        errs.append("첫 슬라이드는 kind가 cover여야 합니다")
    if card.slides[-1].kind != "cta":
        errs.append("마지막 슬라이드는 kind가 cta여야 합니다")
    for i, s in enumerate(card.slides, 1):
        if not s.heading.strip():
            errs.append(f"슬라이드 {i}: heading이 비어 있습니다")
        if len(s.heading) > 60:
            errs.append(f"슬라이드 {i}: heading이 너무 깁니다 ({len(s.heading)}자, 60자 이하)")
        if len(s.highlight) > 8:
            errs.append(f"슬라이드 {i}: highlight가 너무 깁니다 ({len(s.highlight)}자, 8자 이하). 큰 글씨라 줄바꿈되면 한 글자만 남습니다 (예: '월 20만 원')")
        if len(s.body) > 200:
            errs.append(f"슬라이드 {i}: body가 너무 깁니다 ({len(s.body)}자, 200자 이하)")
    if len(card.threads_text) > 500:
        errs.append(f"threads_text가 500자를 넘습니다 ({len(card.threads_text)}자)")
    if not 3 <= len([t for t in card.hashtags if t.strip()]) <= 30:
        errs.append("hashtags는 3~30개여야 합니다")
    if len([s for s in card.sources if s.strip()]) < 2:
        errs.append("sources(출처)가 2개 이상 필요합니다")

    try:
        reel = json.loads((folder / "reel.json").read_text(encoding="utf-8"))
    except Exception as e:
        return errs + [f"reel.json이 JSON이 아닙니다: {e}"]
    style = reel.get("style")
    if style not in STYLES:
        errs.append(f"reel.json style은 {' | '.join(STYLES)} 중 하나여야 합니다 (지금 {style!r})")
    lines = reel.get("lines")
    if not isinstance(lines, list) or not lines:
        errs.append("reel.json lines가 비어 있습니다")
    else:
        slides = []
        for k, ln in enumerate(lines, 1):
            try:
                slides.append(int(ln["slide"]))
                text = str(ln["text"]).strip()
            except Exception:
                errs.append(f"reel.json lines[{k}]에는 slide(숫자)와 text가 있어야 합니다")
                continue
            if not 8 <= len(text.replace("{", "").replace("}", "")) <= 70:
                errs.append(f"내레이션 {k}번째 줄은 8~70자여야 합니다 (지금 {len(text)}자)")
        if sorted(slides) != list(range(1, n + 1)):
            errs.append(f"내레이션 줄은 슬라이드 {n}장에 하나씩(slide 1~{n}) 있어야 합니다")

    blog = (folder / "blog.md").read_text(encoding="utf-8")
    if not blog.lstrip().startswith("# "):
        errs.append("blog.md 첫 줄은 '# 제목' 이어야 합니다")
    if len(blog) < 1200:
        errs.append(f"blog.md가 너무 짧습니다 ({len(blog)}자, 1200자 이상)")

    if style in STYLES:
        for prev in _previous(folder, RECENT):
            try:
                if json.loads((prev / "reel.json").read_text(encoding="utf-8")).get("style") == style:
                    errs.append(f"직전 영상({prev.name})과 같은 스타일입니다. 최근 {RECENT}편과 다른 스타일을 쓰세요")
            except Exception:
                pass
    if style in STYLES and os.environ.get("STYLE_CROSS_AVOID", "true").lower() not in ("0", "false", "no", "off"):
        # 같은 계정에 올라가는 카드뉴스(my-site)가 최근에 쓴 스타일과 같으면 다른 스타일을 권한다.
        # 그러면 고를 스타일이 안 남을 때나 상대 저장소를 읽지 못할 때는 통과시킨다 (있으면 좋은 확인)
        from . import stylefeed

        cross = stylefeed.other_repo_style("youth")
        if cross and cross == style:
            own = set()
            for prev in _previous(folder, RECENT):
                try:
                    own.add(json.loads((prev / "reel.json").read_text(encoding="utf-8")).get("style"))
                except Exception:
                    pass
            options = [n for n in STYLES if n not in own and n != cross]
            if options:
                errs.append(f"같은 계정의 카드뉴스(my-site)가 최근 쓴 스타일({cross})과 같습니다. 다른 스타일을 쓰세요: {' | '.join(options)}")
    for prev in _previous(folder, 14):
        try:
            if TopicIdea.model_validate_json((prev / "topic.json").read_text(encoding="utf-8")).keyword.strip() == topic.keyword.strip():
                errs.append(f"최근 폴더 {prev.name}와 keyword가 같습니다. 새 소재를 고르세요")
        except Exception:
            pass
    return errs


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    folder = Path(argv[0])
    errs = check(folder)
    for e in errs:
        print("✗", e)
    print("통과" if not errs else f"{len(errs)}개 문제가 있습니다")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
