# 루틴 ② 네이버 블로그·클립 발행 (매일 KST 11:50) — Uplika 커넥터가 필요합니다

> 이 루틴은 **claude.ai 루틴 화면에서 직접 만들어야** 합니다 (Uplika 커넥터를 연결해야 해서, 도구로는 만들 수 없습니다).
> 설정: 저장소 `superabba/economypub-youth` 선택, 커넥터 Uplika 연결, 매일 KST 11:50, 모델 Sonnet 5.5.
> 아래 "프롬프트" 부분을 그대로 붙여 넣으세요.

## 프롬프트

경제주막 '청년·사회초년생 정책' 카드뉴스의 **네이버 블로그·클립**을 Uplika로 발행하는 루틴입니다. 인스타·스레드·유튜브 쇼츠는 GitHub Actions가 이미 올렸으니 건드리지 마세요. Uplika 워크스페이스는 `ws_3a45040ee5856407`(economypub)입니다.

1. **오늘 시안 찾기** — 저장소의 `drafts` 브랜치에서 가장 최근 폴더(`YYYYMMDD-HHMM-슬러그`)를 읽습니다 (`git fetch origin drafts` 후 `git show origin/drafts:<폴더>/<파일>`, 또는 GitHub 파일 읽기 도구). 폴더 날짜가 오늘(KST)이 아니면 "오늘 시안 없음"으로 보고하고 끝냅니다.
2. **중복 방지** — Uplika `list_posts`(최근 20건)에 같은 제목의 네이버 블로그 글이 이미 있으면 그 채널은 건너뜁니다.
3. **재료** — 폴더의 `blog.md`(글), `card.json`(슬라이드 6~8장), `caption.txt`, `music.json`(`credit`: 음악 출처 한 줄), `published.json`:
   - `image_urls`: 슬라이드 이미지 공개 주소 (slide_01 ~ slide_NN 순서)
   - `video_urls`: 릴스 영상 공개 주소 (첫 번째를 쓰고, 안 열리면 다음 것)
   - `posts.reels.permalink`(인스타 릴스), `posts.youtube.permalink`(유튜브 쇼츠): 있으면 블로그 글에 링크로 씁니다.
   `published.json`이 없거나 `video_urls`가 비어 있으면 Actions 게시가 아직 안 끝난 것입니다. 10분 간격으로 최대 3번 다시 확인하고, 그래도 없으면 보고하고 끝냅니다.
4. **연결 확인** — `bridge_status`로 네이버 브라우저 확장 프로그램이 연결돼 있는지 봅니다. 연결이 안 돼 있으면 발행하지 말고 "PC가 꺼져 있음"으로 보고합니다(나중에 다시 시도).
5. **네이버 클립** — `media_from_url`로 영상 업로드(altText: 제목, aiGenerated true) 후 `publish`:
   - 글: 핵심 2~3줄(카드뉴스 캡션을 줄여서, 해시태그 제외) + 한 줄 `자세한 내용은 네이버 블로그 '경제주막'에 있어요.` + `music.json`의 `credit`(있을 때만, 맨 끝)
   - `options.naver_clip`: `{"categoryId": "48", "tags": [해시태그 3~5개, 공백 없이], "visibility": "public", "aiGenerated": true, "adDisclosure": false}`
6. **네이버 블로그** — 슬라이드 이미지를 `media_from_url`로 올리고(altText: 각 슬라이드 제목), `blog.md`를 Uplika 네이버 형식으로 바꿔 `publish`합니다.
   - 첫 줄 `# 제목`은 `options.naver_blog.title`로 옮기고 본문에서는 뺍니다.
   - 본문 맨 위에 대표 이미지(slide_01) → 도입 문단 → `▶ 30초 쇼츠로 먼저 보기: [유튜브 쇼츠](주소) · [인스타 릴스](주소)` (둘 중 있는 것만).
   - `## 소제목`은 `> 소제목{.underline}` 로, 섹션 사이에는 `---{.line1}` 줄을 넣고, 섹션마다 슬라이드 이미지를 `![소제목](media:ID)` 로 넣습니다.
   - FAQ(`**Q. …**` / `A. …`), 마무리, `**참고 자료**` 목록은 그대로 유지합니다.
   - `options.naver_blog`: `{"title": 제목, "categoryId": "2", "tags": [10~15개, 공백 없이], "openType": "public", "layout": "template", "form": "photo-story"}`
7. **보고** — 발행한 채널, 제목, 링크(또는 접수 상태)를 한국어로 보고합니다. 실패하면 에러 코드와 원인을 그대로 적고, 같은 글을 두 번 올리지 마세요(재시도 전 `list_posts`로 확인).

규칙: 사실이 불확실한 문장을 새로 만들지 마세요. 원고에 없는 숫자·날짜를 추가하지 않습니다. 네이버 태그에는 공백이 들어가면 안 됩니다.
