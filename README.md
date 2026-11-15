# economypub-youth

경제주막 **청년·사회초년생 정책** 카드뉴스 실험 저장소. 기존 카드뉴스 봇(`superabba/my-site`)과 별개이며, **LLM API를 쓰지 않는다.**

## 구조
```
Claude 루틴 ① (KST 10:40)   웹 검색으로 소재를 고르고 원고를 content/<날짜-주제>/ 에 JSON·글로 올림   ← API 키 대신 Claude 루틴이 글쓰기를 맡음
        │ push (main, content/**)
        ▼
GitHub Actions (render.yml)   원고 → 카드 이미지 + 릴스 영상(여성 내레이션·배경음악·스타일) → drafts 브랜치   ← 키 없이 돈다
        ▼
(2단계) Claude 루틴 ② (KST 11:30)   Uplika로 인스타·스레드·유튜브 쇼츠·네이버 블로그·네이버 클립 발행
```
- 1단계(현재): 2단계 없이 **시안(이미지·영상)까지만** 만들어 API 없이 도는지 확인한다.
- `cardnews-bot/` 는 기존 봇의 렌더링 부분(카드 이미지, 릴스 엔진, 배경음악)만 복사한 것이다. LLM·트렌드 수집·게시 코드는 뺐다.
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
