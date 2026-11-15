import os
import shutil
import subprocess
import sys

import pytest
from conftest import make_content

from cardbot import content, lemoreel, validate_content


def test_valid_folder_passes(content_root):
    d = make_content(content_root, "20261116-a")
    assert validate_content.check(d) == []


def test_missing_files_and_bad_shapes_are_reported(content_root):
    d = make_content(content_root, "20261116-a")
    (d / "blog.md").unlink()
    assert any("blog.md" in e for e in validate_content.check(d))
    d2 = make_content(content_root, "20261117-b", n=4)
    errs = validate_content.check(d2)
    assert any("5~9장" in e for e in errs)


def test_style_and_keyword_rotation_enforced(content_root):
    make_content(content_root, "20261116-a", style="caption-news", keyword="a")
    make_content(content_root, "20261117-b", style="chalkboard", keyword="b")
    same_as_prev = make_content(content_root, "20261118-c", style="chalkboard", keyword="c")
    assert any("같은 스타일" in e for e in validate_content.check(same_as_prev))
    shutil.rmtree(same_as_prev)  # 잘못된 시도는 올리지 않았다고 치고 지운다
    same_as_two_back = make_content(content_root, "20261118-c", style="caption-news", keyword="c")
    assert any("같은 스타일" in e for e in validate_content.check(same_as_two_back))
    shutil.rmtree(same_as_two_back)
    ok = make_content(content_root, "20261118-c", style="swiss-motion", keyword="c")
    assert validate_content.check(ok) == []
    dup = make_content(content_root, "20261119-d", style="caption-news", keyword="c")  # 스타일은 맞지만 keyword가 같음
    assert any("keyword가 같습니다" in e for e in validate_content.check(dup))
    assert not any("같은 스타일" in e for e in validate_content.check(dup))


def test_beat_style_is_rejected(content_root):
    d = make_content(content_root, "20261116-a", style="caption-beat")
    assert any("style" in e for e in validate_content.check(d))


def test_fixed_writer_returns_the_planned_narration_without_any_llm(content_root):
    d = make_content(content_root, "20261116-a")
    topic, card, plan = content.load(d)
    w = content.FixedWriter(plan)
    out = lemoreel.plan_reel(w, topic, card, forced_style=plan.style)
    assert out.style == "caption-news" and len(out.lines) == len(card.slides)
    with pytest.raises(RuntimeError):
        w._parse("s", "u", dict)


def test_pending_lists_only_unrendered(content_root, tmp_path):
    make_content(content_root, "20261116-a")
    make_content(content_root, "20261117-b", style="chalkboard", keyword="b")
    out = tmp_path / "out"
    (out / "20261116-a").mkdir(parents=True)
    (out / "20261116-a" / "reel.mp4").write_bytes(b"x")
    assert [p.name for p in content.pending(content_root, out)] == ["20261117-b"]


def test_no_llm_sdk_is_imported_or_required():
    """anthropic·google-genai가 없어도 전부 불러와져야 한다 (이 저장소에는 설치하지 않는다)."""
    code = "import sys; import cardbot.content, cardbot.validate_content; bad=[m for m in sys.modules if m.split('.')[0] in ('anthropic','google','openai')]; sys.exit(1 if bad else 0)"
    assert subprocess.run([sys.executable, "-c", code], cwd=os.path.join(os.path.dirname(__file__), "..")).returncode == 0


@pytest.mark.skipif(os.environ.get("LEMO_E2E") != "1", reason="브라우저 렌더링(수 분)이라 LEMO_E2E=1일 때만")
def test_render_folder_end_to_end(content_root, tmp_path, monkeypatch):
    monkeypatch.setenv("REELS_FAKE_TTS", "1")
    monkeypatch.setenv("REELS_FPS", "6")
    d = make_content(content_root, "20261116-a")
    out = content.render_folder(d, tmp_path / "out")
    for name in ("slide_01.jpg", "reel.mp4", "reel_cover.jpg", "music.json", "caption.txt", "threads.txt", "blog.md"):
        assert (out / name).exists(), name
    assert (out / "reel.mp4").stat().st_size > 10_000
