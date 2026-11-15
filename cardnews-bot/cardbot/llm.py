"""카드뉴스 원고의 데이터 형식(스키마)과 정리 함수.

이 저장소에는 LLM(API) 호출이 없다. 원고는 Claude 루틴이 content/ 폴더에 JSON으로 써 두고,
여기서는 그 JSON을 읽어 이미지·영상으로 만들기만 한다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

class TopicIdea(BaseModel):
    title: str  # 카드뉴스 작업 제목
    keyword: str  # 근거가 된 트렌드 키워드
    angle: str  # 어떤 관점/형식으로 풀지 (예: 체크리스트, 비교, 오해와 진실)
    hook: str  # 첫 장에 들어갈 후킹 문구 초안
    why_now: str  # 지금 조회수가 나올 이유
    score: int  # 0~100, 예상 반응 점수
    risk: str  # 사실확인·민감성 리스크 (없으면 빈 문자열)


class TopicList(BaseModel):
    topics: list[TopicIdea]


class Slide(BaseModel):
    kind: Literal["cover", "content", "summary", "cta"]
    heading: str
    body: str
    highlight: str  # 크게 강조할 짧은 문구나 숫자 (없으면 빈 문자열)


class CardNews(BaseModel):
    slides: list[Slide]
    caption: str  # 인스타그램 캡션 (해시태그 제외)
    hashtags: list[str]  # '#' 없이
    threads_text: str  # 스레드 본문 (500자 이내)
    sources: list[str]  # 참고한 출처 URL/매체명


class BlogSection(BaseModel):
    heading: str  # 소제목
    body: str  # 문단은 빈 줄(\n\n)로 구분
    image: str  # 넣을 카드뉴스 이미지 파일명 (예: slide_02.jpg), 없으면 빈 문자열
    experience_hint: str  # 글쓴이가 직접 덧붙이면 좋을 경험/의견 안내 (없으면 빈 문자열)


class BlogFAQ(BaseModel):
    question: str
    answer: str


class BlogPost(BaseModel):
    titles: list[str]  # 제목 후보 (첫 번째가 추천)
    main_keyword: str
    sub_keywords: list[str]
    meta_description: str  # 검색 결과 요약문 (티스토리 요약/설명용)
    intro: str
    sections: list[BlogSection]
    faq: list[BlogFAQ]
    conclusion: str
    tags: list[str]  # '#' 없이
    sources: list[str]


# ---------- 프롬프트 ----------


def normalize(card: CardNews, lo: int, hi: int) -> CardNews:
    """플랫폼 제약에 맞게 정리 (캐러셀 2~10장, 스레드 500자, 해시태그 30개)."""
    slides = card.slides[:hi]
    if slides and slides[-1].kind != "cta" and any(s.kind == "cta" for s in card.slides):
        slides[-1] = next(s for s in reversed(card.slides) if s.kind == "cta")
    if len(slides) < max(2, lo):
        raise ValueError(f"슬라이드가 너무 적습니다: {len(slides)}장")
    tags = []
    for t in card.hashtags:
        t = t.strip().lstrip("#").replace(" ", "")
        if t and t not in tags:
            tags.append(t)
    threads = card.threads_text.strip()
    if len(threads) > 500:
        threads = threads[:499].rstrip() + "…"
    return card.model_copy(update={"slides": slides, "hashtags": tags[:30], "threads_text": threads})


def normalize_blog(post: BlogPost, images: list[str]) -> BlogPost:
    """존재하지 않는 이미지 참조 제거, 태그 정리 (네이버 최대 30개)."""
    allowed = set(images)
    sections = [
        sec.model_copy(update={"image": sec.image if sec.image in allowed else ""})
        for sec in post.sections
    ]
    tags = []
    for t in post.tags:
        t = t.strip().lstrip("#").replace(" ", "")
        if t and t not in tags:
            tags.append(t)
    if not post.titles or not sections:
        raise ValueError("블로그 글에 제목이나 본문이 없습니다")
    return post.model_copy(update={"sections": sections, "tags": tags[:30]})


def instagram_caption(card: CardNews) -> str:
    tags = " ".join(f"#{t}" for t in card.hashtags)
    cap = f"{card.caption.strip()}\n\n{tags}".strip()
    return cap[:2200]
