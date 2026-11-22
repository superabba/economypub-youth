# economypub-youth

경제주막 **청년·사회초년생 정책** 카드뉴스 실험 저장소. 기존 카드뉴스 봇(`superabba/my-site`)과 별개이며, **LLM API를 쓰지 않는다.**

## 구조
```
Claude 루틴 ① (KST 10:40)   웹 검색으로 소재를 고르고 원고를 content/<날짜-주제>/ 에 JSON·글로 올림   ← API 키 대신 Claude 루틴이 글쓰기를 맡음
        │ push (main, content/**)
        ▼
Actions: render.yml          원고 → 카드 이미지 + 릴스 영상(여성 내레이션·배경음악·스타일) → drafts 브랜치      ← 키 없이 돈다
        ▼
Actions: publish.yml (KST 11:30)   인스타(카드뉴스·릴스)·스레드·유튜브 쇼츠에 각 서비스 토큰으로 직접 게시 → published.json 기록
        ▼
Claude 루틴 ② (KST 11:50)   Uplika로 네이버 블로그·네이버 클립 게시 (published.json 의 영상·이미지 주소 사용)   ← routine/publish_naver.md
```
- **게시 방식은 기존 카드뉴스 봇과 같다**: 인스타·스레드·유튜브는 Actions가 토큰으로 직접 올리고, 네이버 블로그·클립만 Uplika(루틴)가 올린다.
- `publish.yml` 은 기본이 **시험 실행**(올리지 않고 무엇을 올릴지만 출력)이다. 저장소 변수 `AUTO_PUBLISH=true` 를 넣어야 예약 실행이 실제로 올린다. 수동 실행은 `dry_run` 입력을 따른다.
- 필요한 Secrets: `IG_USER_ID`, `IG_ACCESS_TOKEN`, `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` (my-site 와 같은 계정이면 같은 값). **LLM(API) 키는 넣지 않는다.**
- 선택 Variables: `PLATFORMS`(기본 instagram,reels,threads + 유튜브 인증값이 있으면 youtube), `YOUTUBE_PRIVACY`(기본 private), `AUTO_PUBLISH`.
- `cardnews-bot/` 는 기존 봇의 렌더링·게시 부분(카드 이미지, 릴스 엔진, 배경음악, 인스타·스레드·유튜브 게시)만 복사한 것이다. LLM·트렌드 수집 코드는 뺐다.
- 스타일은 직전 두 편과 다르게(`caption-news`, `chalkboard`, `swiss-motion`) 돌린다. 검증 스크립트가 막는다.

## API 없이 돈다는 것을 확인하는 방법
- `requirements.txt` 에 anthropic·google-genai 가 없고, 워크플로 첫 단계가 환경에 LLM API 키가 있으면 실패한다.
- 이 저장소의 Settings → Secrets 에는 LLM 키를 등록하지 않는다.
- `python -m pytest cardnews-bot/tests` 에 LLM SDK를 불러오지 않는다는 시험이 있다.

## 로컬에서 해 보기
```bash
cd cardnews-bot && pip install -r requirements.txt && (cd reelstudio && npm ci)
python -m cardbot.validate_content ../content/<폴더>   # 원고 형식 확인
python -m cardbot render <폴더>                        # content/ → ../out/
LEMO_E2E=1 REELS_FAKE_TTS=1 python -m pytest tests     # 브라우저 렌더링 시험 (가짜 목소리)
```

## 인스타 카드 슬라이드는 올리지 않음
인스타그램 **카드 슬라이드(캐러셀) 게시는 꺼져 있습니다.** 릴스·스레드·유튜브 쇼츠는 그대로 올라갑니다. `PLATFORMS` 변수에 `instagram` 이 들어 있어도 무시되며, 다시 올리려면 저장소 Variables 에 `INSTAGRAM_CAROUSEL=true` 를 넣으세요. (스레드는 같은 슬라이드를 캐러셀로 올립니다.)

## 스레드·네이버 블로그 이미지는 릴스 영상 캡처
스레드 캐러셀과 네이버 블로그에는 카드 슬라이드 대신 **릴스 영상의 장면 캡처**(`frame_01.jpg` …, 1080×1920)를 씁니다. 렌더링 때 릴스를 만든 뒤 컷마다 내레이션이 70% 읽힌 시점(`reel_plan.json` 의 `frames`)의 화면을 캡처하고, 게시할 때 그 캡처를 올려 `published.json` 의 `image_urls` 에 기록합니다. 네이버 루틴 ②는 이 주소를 읽으므로 캡처를 씁니다. 릴스 영상이 없으면 슬라이드를 씁니다. 인스타 카드 슬라이드를 다시 켜면(`INSTAGRAM_CAROUSEL=true`) 캐러셀에는 슬라이드 원본(`slide_urls`)을 따로 올립니다.

## 네이버 블로그 이미지: 첫 장 1:1, 나머지 4:5
네이버 블로그 피드는 글의 첫 이미지를 **정사각형(1:1)으로 잘라** 썸네일로 보여 줍니다. 그래서 블로그용 이미지 `blog_NN.jpg` 는 릴스 캡처에서 **글자가 있는 세로 구간만 가로 꽉 차게 잘라** 만듭니다: 첫 장은 **1080×1080**(썸네일 안 잘림), 나머지는 **1080×1350(4:5)**. `published.json` 의 `image_urls` 가 이 주소이고(네이버 루틴 ②가 읽음), 스레드 캐러셀은 세로 캡처 주소 `threads_image_urls` 를 씁니다.
