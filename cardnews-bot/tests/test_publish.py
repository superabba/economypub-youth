import json
from datetime import datetime, timezone, timedelta

from conftest import make_content

from cardbot import publish
from cardbot.config import Settings
from cardbot.publishers import PublishResult

KST = timezone(timedelta(hours=9))


class FakePub:
    def __init__(self, name, needs_video=False, fail=False):
        self.name, self.needs_video, self.fail = name, needs_video, fail
        self.calls = []

    def publish(self, assets, text):
        self.calls.append((assets, text))
        if self.fail:
            raise RuntimeError("토큰 만료")
        return PublishResult(platform=self.name, media_id=f"{self.name}-1", permalink=f"https://example.com/{self.name}")


class FakeHost:
    def upload(self, files, folder):
        if len(files) == 2:
            return "https://cdn.example.com/reel.mp4", "https://cdn.example.com/cover.jpg"
        return [f"https://cdn.example.com/{f.name}" for f in files]

    def candidates(self, url):
        return [url]


def rendered(tmp_path, name="20261116-1040-a", credit=True):
    """content 폴더를 렌더링 결과처럼 꾸민다 (이미지·영상·캡션·음악 출처)."""
    d = make_content(tmp_path, name)
    for i in range(1, 7):
        (d / f"slide_{i:02d}.jpg").write_bytes(b"x")
    (d / "reel.mp4").write_bytes(b"x")
    (d / "reel_cover.jpg").write_bytes(b"x")
    (d / "caption.txt").write_text("청년 월세 지원 캡션\n\n#청년월세 #청년지원", encoding="utf-8")
    (d / "threads.txt").write_text("스레드 글", encoding="utf-8")
    line = "🎵 Vibe Ace - Kevin MacLeod (CC BY 3.0, 편집) http://example.com" if credit else ""
    (d / "music.json").write_text(json.dumps({"credit": line}), encoding="utf-8")
    return d


def test_dry_run_posts_nothing_and_writes_nothing(tmp_path):
    d = rendered(tmp_path)
    pubs = [FakePub("instagram"), FakePub("reels", True), FakePub("threads"), FakePub("youtube")]
    plan = publish.publish_folder(d, Settings(), dry_run=True, publishers=pubs)
    assert plan["platforms"] == ["instagram", "reels", "threads", "youtube"] and plan["images"] == 6
    assert all(not p.calls for p in pubs) and not (d / "published.json").exists()


def test_publish_records_posts_adds_credit_everywhere_except_threads(tmp_path):
    d = rendered(tmp_path)
    ig, reels, th, yt = FakePub("instagram"), FakePub("reels", True), FakePub("threads"), FakePub("youtube")
    meta = publish.publish_folder(d, Settings(), host=FakeHost(), publishers=[ig, reels, th, yt])
    assert set(meta["posts"]) == {"instagram", "reels", "threads", "youtube"} and meta["failures"] == []
    assert "Vibe Ace" in ig.calls[0][1] and "Vibe Ace" in reels.calls[0][1] and "Vibe Ace" in yt.calls[0][1]
    assert "Vibe Ace" not in th.calls[0][1] and th.calls[0][1] == "스레드 글"
    assert meta["image_urls"][0].startswith("https://cdn.example.com/") and meta["video_urls"] == ["https://cdn.example.com/reel.mp4"]
    assert yt.calls[0][0]["video_path"].endswith("reel.mp4") and "#청년월세" in yt.calls[0][0]["hashtags"]


def test_rerun_skips_done_platforms_and_retries_failed_ones(tmp_path):
    d = rendered(tmp_path)
    bad = FakePub("youtube", fail=True)
    ig = FakePub("instagram")
    meta = publish.publish_folder(d, Settings(), host=FakeHost(), publishers=[ig, bad])
    assert "instagram" in meta["posts"] and meta["failures"] and "youtube" not in meta["posts"]
    ig2, ok = FakePub("instagram"), FakePub("youtube")
    meta = publish.publish_folder(d, Settings(), host=FakeHost(), publishers=[ig2, ok])
    assert not ig2.calls and ok.calls and meta["failures"] == [] and "youtube" not in meta.get("errors", {})


def test_latest_unpublished_picks_newest_and_respects_age(tmp_path):
    s = Settings()
    s.platforms = ["instagram", "reels", "threads"]
    old = rendered(tmp_path, "20261114-1040-old")
    new = rendered(tmp_path, "20261116-1040-new")
    now = datetime(2026, 11, 16, 11, 30, tzinfo=KST)
    assert publish.latest_unpublished(tmp_path, s, now) == new
    (new / "published.json").write_text(json.dumps({"posts": {p: {} for p in s.platforms}}), encoding="utf-8")
    assert publish.latest_unpublished(tmp_path, s, now) is None  # 최신 폴더를 이미 다 올렸으면 옛 폴더는 건드리지 않는다
    assert publish.latest_unpublished(tmp_path, s, datetime(2026, 11, 20, 11, 30, tzinfo=KST)) is None  # 너무 오래됨
    assert old.exists()
