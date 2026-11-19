import json
from pathlib import Path

import pytest


def make_content(root: Path, name: str, style: str = "caption-news", keyword: str = "청년 월세 지원", n: int = 6) -> Path:
    """검증·렌더링 시험용 원고 폴더."""
    d = root / name
    d.mkdir(parents=True)
    (d / "topic.json").write_text(json.dumps({
        "title": "청년 월세 지원 신청 전 꼭 볼 3가지", "keyword": keyword, "angle": "체크리스트", "hook": "신청 기간 놓치면 못 받아요",
        "why_now": "이번 달 신청 마감", "score": 70, "risk": ""}, ensure_ascii=False), encoding="utf-8")
    slides = [{"kind": "cover", "heading": "청년 월세 지원, 신청 전 3가지", "body": "놓치면 월 20만 원이 날아가요", "highlight": "월 20만 원"}]
    for i in range(n - 2):
        slides.append({"kind": "content", "heading": f"포인트 {i + 1}: 소득 기준 확인", "body": "중위소득 기준과 보증금 한도를 먼저 확인하세요.", "highlight": ""})
    slides.append({"kind": "cta", "heading": "저장해 두고 신청일에 꺼내 보세요", "body": "친구에게도 공유해 주세요", "highlight": ""})
    (d / "card.json").write_text(json.dumps({
        "slides": slides, "caption": "청년 월세 지원, 이것만 확인하세요", "hashtags": ["청년월세", "청년지원", "사회초년생"],
        "threads_text": "청년 월세 지원 신청 전에 확인할 3가지를 정리했어요.", "sources": ["복지로 (bokjiro.go.kr)", "국토교통부 보도자료"]},
        ensure_ascii=False), encoding="utf-8")
    (d / "reel.json").write_text(json.dumps({
        "style": style, "reason": "제도 안내", "card_mid": "", "card_last": "",
        "lines": [{"slide": i + 1, "text": f"{i + 1}번째 내레이션이에요. 월 {i + 1}0만 원을 확인해 보세요."} for i in range(n)]},
        ensure_ascii=False), encoding="utf-8")
    (d / "blog.md").write_text("# 청년 월세 지원 신청 전 확인할 3가지\n\n" + "본문 문단입니다. 소득 기준과 보증금 한도를 확인하세요.\n\n" * 60, encoding="utf-8")
    return d


@pytest.fixture
def content_root(tmp_path):
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture(autouse=True)
def _no_network_style_feed(monkeypatch):
    """기본 시험은 상대 저장소를 읽지 않는다 (필요한 시험이 따로 켠다)."""
    monkeypatch.setenv("STYLE_CROSS_AVOID", "false")
