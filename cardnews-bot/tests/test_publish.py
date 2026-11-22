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


def test_check_credentials_reports_each_platform_without_posting():
    class Graph:
        def __init__(self, ok): self.ok = ok
        def get(self, path, **params):
            if not self.ok:
                raise RuntimeError("토큰 만료")
            return {"username": "economypub"}

    class P:
        def __init__(self, name, ok=True): self.name, self.user_id, self.api = name, "1", Graph(ok)

    class YT:
        name, channel_id = "youtube", "UC_other"
        def my_channel(self): return "UC_mine", "경제주막"

    res = publish.check_credentials(Settings(), publishers=[P("instagram"), P("reels"), P("threads", ok=False), YT()])
    assert list(res) == ["instagram", "threads", "youtube"]  # 릴스는 인스타와 같은 계정이라 한 번만
    assert res["instagram"].startswith("정상") and res["threads"].startswith("실패") and "경고" in res["youtube"]


# ---------------------------------------------------------------- 인스타 카드 슬라이드(캐러셀)는 올리지 않는다

def test_instagram_carousel_off_by_default(monkeypatch):
    from cardbot.config import Settings
    for k in ("PLATFORMS", "INSTAGRAM_CAROUSEL", "YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.setenv(k, "")
    s = Settings.load()
    assert "instagram" not in s.platforms and {"reels", "threads"} <= set(s.platforms)


def test_instagram_in_platforms_variable_is_stripped_unless_enabled(monkeypatch):
    from cardbot.config import Settings
    monkeypatch.setenv("PLATFORMS", "instagram,reels,threads,youtube")
    monkeypatch.setenv("INSTAGRAM_CAROUSEL", "")
    assert Settings.load().platforms == ["reels", "threads", "youtube"]
    monkeypatch.setenv("INSTAGRAM_CAROUSEL", "true")
    assert Settings.load().platforms == ["instagram", "reels", "threads", "youtube"]


# ---------------------------------------------------------------- 스레드·블로그 이미지는 릴스 영상 캡처

def _real_reel(folder, seconds=6):
    import subprocess

    from cardbot.frames import _ffmpeg
    subprocess.run([_ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=s=270x480:d={seconds}:r=10",
                    "-pix_fmt", "yuv420p", str(folder / "reel.mp4")], check=True)


def test_publish_uses_square_images_for_naver_and_reel_frames_for_threads(tmp_path):
    from PIL import Image
    d = rendered(tmp_path)
    _real_reel(d)
    (d / "reel_plan.json").write_text(json.dumps({"frames": [1.0, 3.0, 5.0]}), encoding="utf-8")
    th = FakePub("threads")
    meta = publish.publish_folder(d, Settings(), host=FakeHost(), publishers=[th])
    # published.json → 네이버 루틴이 읽는 주소: 정사각형 (피드 썸네일이 1:1 이라 세로 그림은 잘린다)
    assert [u.rsplit("/", 1)[-1] for u in meta["image_urls"]] == ["blog_01.jpg", "blog_02.jpg", "blog_03.jpg"]
    assert all(Image.open(p).size == (1080, 1080) for p in d.glob("blog_*.jpg"))
    # 스레드 캐러셀: 세로 영상 캡처
    assert [u.rsplit("/", 1)[-1] for u in th.calls[0][0]["threads_image_urls"]] == ["frame_01.jpg", "frame_02.jpg", "frame_03.jpg"]


def test_publish_falls_back_to_slides_without_a_playable_reel(tmp_path):
    d = rendered(tmp_path)      # reel.mp4 가 영상이 아니다
    th = FakePub("threads")
    meta = publish.publish_folder(d, Settings(), host=FakeHost(), publishers=[th])
    assert [u.rsplit("/", 1)[-1] for u in meta["image_urls"]][0] == "slide_01.jpg"


def test_instagram_carousel_gets_slides_not_squares_when_reenabled(tmp_path):
    d = rendered(tmp_path)
    _real_reel(d)
    (d / "reel_plan.json").write_text(json.dumps({"frames": [1.0, 3.0, 5.0]}), encoding="utf-8")
    ig = FakePub("instagram")
    meta = publish.publish_folder(d, Settings(), host=FakeHost(), publishers=[ig])
    assert [u.rsplit("/", 1)[-1] for u in ig.calls[0][0]["slide_urls"]][0] == "slide_01.jpg"
    assert meta["image_urls"][0].endswith("blog_01.jpg")


def test_square_fit_is_1080_square_and_keeps_everything():
    from PIL import Image

    from cardbot.frames import square_fit
    for size in ((1080, 1920), (1080, 1350), (1376, 768), (1000, 1000)):
        assert square_fit(Image.new("RGB", size, (200, 30, 30))).size == (1080, 1080)
