"""사용: python -m cardbot render [폴더이름]  (content/ 의 원고 → out/ 의 이미지·영상. 폴더를 안 주면 아직 안 만든 것 전부)"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import content


def main() -> int:
    ap = argparse.ArgumentParser(prog="cardbot", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="원고를 이미지·영상으로 만든다")
    r.add_argument("folder", nargs="?", default="", help="content/ 안의 폴더 이름 (비우면 아직 안 만든 폴더 전부)")
    sub.add_parser("pending", help="아직 영상이 없는 원고 폴더를 보여 준다")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.cmd == "pending":
        for d in content.pending():
            print(d.name)
        return 0
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
