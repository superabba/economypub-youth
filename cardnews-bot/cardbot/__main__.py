"""사용: python -m cardbot render [폴더이름]  (content/ 의 원고 → out/ 의 이미지·영상. 폴더를 안 주면 아직 안 만든 것 전부)"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pathlib import Path as _P

from . import content
from .config import Settings
from . import publish as pub


def main() -> int:
    ap = argparse.ArgumentParser(prog="cardbot", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="원고를 이미지·영상으로 만든다")
    r.add_argument("folder", nargs="?", default="", help="content/ 안의 폴더 이름 (비우면 아직 안 만든 폴더 전부)")
    sub.add_parser("pending", help="아직 영상이 없는 원고 폴더를 보여 준다")
    q = sub.add_parser("publish", help="렌더링된 시안을 인스타·스레드·유튜브 쇼츠에 올린다 (토큰 사용, LLM 없음)")
    q.add_argument("folder", nargs="?", default="", help="시안 폴더 경로. --latest 와 같이 쓰지 않는다")
    q.add_argument("--latest", action="store_true", help="--dir 안에서 가장 최근의 아직 안 올린 폴더")
    q.add_argument("--dir", default="", help="--latest 가 찾아볼 시안 모음 폴더 (예: ../drafts)")
    q.add_argument("--dry-run", action="store_true", help="올리지 않고 무엇을 올릴지만 보여 준다")
    q.add_argument("--check", action="store_true", help="토큰이 통하는지 읽기 전용으로만 확인한다 (아무것도 올리지 않는다)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.cmd == "pending":
        for d in content.pending():
            print(d.name)
        return 0
    if a.cmd == "publish":
        s = Settings.load()
        if a.check:
            res = pub.check_credentials(s)
            for k, v in res.items():
                print(f"{k}: {v}")
            return 0 if res and all(v.startswith("정상") for v in res.values()) else 1
        folder = _P(a.folder) if a.folder else (pub.latest_unpublished(_P(a.dir), s) if a.latest else None)
        if not folder:
            print("올릴 시안이 없습니다")
            return 0
        meta = pub.publish_folder(folder, s, dry_run=a.dry_run)
        print(f"완료: {folder.name}")
        return 1 if (not a.dry_run and meta.get("failures")) else 0
    targets = [content.CONTENT_ROOT / a.folder] if a.folder else content.pending()
    if not targets:
        print("만들 원고가 없습니다")
        return 0
    fails = 0
    for src in targets:
        try:
            out = content.render_folder(src)
            print(f"완료: {out}")
        except Exception as e:  # 한 폴더가 실패해도 나머지는 계속
            fails += 1
            logging.getLogger("cardbot").error("%s 실패: %s", src.name, e)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
