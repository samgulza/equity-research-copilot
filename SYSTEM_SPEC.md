# Equity Research Copilot System Spec

작성일: 2026-05-21  
상태: MVP 운영 중, GitHub Pages 정적 리포트 배포 가능

## 1. 시스템 정의

Equity Research Copilot은 공개 가격 데이터, 뉴스, 공시, 차트 구조, 트레이딩 셋업 신호를 결합해 매일 종목 감시 리포트를 생성하는 리서치 보조 시스템이다.

이 시스템은 자동매매 봇이 아니다. 핵심 목적은 다음이다.

- 종목 후보를 동적으로 발굴한다.
- 뉴스 전문, 공시, 차트가 같은 방향을 가리키는지 검증한다.
- 촉매 뉴스가 실제 해당 종목과 직접 관련되는지 필터링한다.
- 차트 기반 진입/손절/목표/손익비를 산출한다.
- 날짜별 리포트 스냅샷을 저장한다.
- 전일 후보가 다음날 어떻게 움직였는지 outcome을 기록한다.
- GitHub Pages에서 모바일 친화적인 HTML 리포트로 확인한다.

## 2. 시스템 경계

### 포함 범위

- 미국 주식 후보 발굴
- 한국 주식 후보 발굴
- OpenBB/yfinance 기반 OHLCV 수집
- Naver Search News API 기반 한국 뉴스 수집
- OpenBB company news 및 SEC filing 수집
- 뉴스 catalyst 추출과 점수화
- 기사 전문 추출, canonical URL, content hash 저장
- source tier, evidence span, counter-evidence, metric mention 저장
- market reaction score 산출
- 기업명/티커 직접성 기반 뉴스 필터
- SMA/RSI/MACD/ATR/거래량 기반 차트 분석
- 돌파/눌림/롱감시/추격회피/리스크감시 셋업 산출
- Markdown/PDF 리서치 메모 생성
- Chart.js 정적 HTML 대시보드 생성
- 날짜별 JSON 아카이브와 전일 outcome 비교
- GitHub Pages 배포

### 제외 범위

- broker API 연결
- 실제 주문 실행
- position sizing 자동화
- 카피트레이딩 실행
- 투자 자문 또는 매수/매도 추천
- 원격 AI-Trader 플랫폼 자동 등록
- 사용자 계좌/포지션 관리

## 3. 주요 사용자

- 매일 시장 후보를 빠르게 훑어보는 개인 리서치 사용자
- 뉴스와 차트를 한 화면에서 같이 보고 싶은 사용자
- 전일 가설이 다음날 맞았는지 기록하려는 사용자
- 자동매매보다 리서치 기록과 검증을 우선하는 사용자

## 4. 실행 흐름

```text
1. 후보 수집
   OpenBB discovery + Naver Finance list

2. 가격 데이터 수집
   OpenBBAdapter -> normalized OHLCV DataFrame

3. 기술 지표 계산
   SMA20/SMA50/SMA100, RSI14, MACD, ATR14, volume_20d

4. 차트 구조 분석
   trend/range/downtrend, support, resistance, momentum, volume state

5. 트레이딩 셋업 분석
   breakout, pullback, base, extended, risk_distribution

6. 뉴스 수집
   OpenBB company news, SEC filing, Naver Search News, Naver Finance item news,
   optional GDELT/RSS/company IR feeds

7. 기사 전문 추출
   trafilatura/HTML fallback으로 body, metadata, content hash, canonical URL 저장

8. 뉴스 직접성 / entity-linked 필터
   제목, 요약, 본문에서 기업명/티커/alias 직접성을 확인

9. Catalyst 생성
   event type/subtype, driver, direction, metrics, evidence span, counter-evidence,
   materiality, novelty, priced-in risk

10. Market reaction 분석
   abnormal return, volume z-score, gap reaction으로 선반영 가능성 산출

11. 후보 점수화
   source score + technical score + setup score + catalyst score - risk penalty

12. 산출물 생성
   discovery CSV/Markdown/PDF, 종목별 memo/chart pack, 정적 JSON/HTML

13. 아카이브 및 검증
   docs/data/YYYY-MM-DD.json 저장, 전일 후보 outcome 계산,
   event/setup/news-quality별 hit rate 평가

14. 배포
   docs/ -> GitHub Pages
```

## 5. 주요 명령

### 일일 리프레시

```bash
scripts/run_daily_static_report.sh
```

역할:

- `research-copilot discover` 실행
- 상위 후보 상세 분석
- `docs/report-data.json` 생성
- `docs/data/YYYY-MM-DD.json` 생성
- `docs/data/index.json` 갱신
- 전일 스냅샷이 있으면 outcome 비교 생성

### 정적 리포트만 재생성

```bash
python scripts/export_static_research_site.py --top 12
```

### 단일 종목 분석

```bash
research-copilot analyze NVDA --days 180 --format both --with-fundamentals --with-news --include-sec
```

### 동적 후보 발굴

```bash
research-copilot discover --universe all --candidate-limit 25 --top 10 --analyze-top 3 --format md
```

### 아카이브 기반 event 평가

```bash
research-copilot evaluate-events --archive-dir docs/data --out-dir runs
```

## 6. 데이터 입력

| 입력 | 출처 | 구현 위치 |
|---|---|---|
| OHLCV | OpenBB/yfinance | `src/equity_research_copilot/adapters/openbb_adapter.py` |
| 미국 후보군 | OpenBB discovery | `src/equity_research_copilot/discovery.py` |
| 한국 후보군 | Naver Finance scrape | `src/equity_research_copilot/discovery.py` |
| 미국 뉴스 | OpenBB company news | `src/equity_research_copilot/adapters/news_adapter.py` |
| SEC filing | OpenBB SEC endpoint | `src/equity_research_copilot/adapters/news_adapter.py` |
| 한국 뉴스 | Naver Search News API | `src/equity_research_copilot/adapters/news_adapter.py` |
| 한국 종목 뉴스 | Naver Finance item news | `src/equity_research_copilot/adapters/news_adapter.py` |
| 글로벌 뉴스 discovery | GDELT DOC API, optional | `src/equity_research_copilot/adapters/news_adapter.py` |
| RSS/회사 IR | 환경변수 feed list | `src/equity_research_copilot/adapters/news_adapter.py` |
| 기사 전문 | trafilatura + HTML fallback | `src/equity_research_copilot/news/article.py` |

## 7. 핵심 모듈

| 모듈 | 책임 |
|---|---|
| `discovery.py` | 후보 수집, 뉴스/차트/셋업/촉매 점수 결합 |
| `adapters/openbb_adapter.py` | OpenBB 가격/펀더멘털 호출 격리 |
| `adapters/news_adapter.py` | 뉴스/공시 수집 |
| `news/article.py` | URL canonicalization, full-text extraction, metadata/hash 저장 |
| `news/relevance.py` | 기업명/티커 직접성 필터, 저신호 제목 제거 |
| `news/event_extractor.py` | event type/subtype, driver, evidence span, metric mention 추출 |
| `news/clustering.py` | 기사/event clustering과 novelty 계산 |
| `news/counter_evidence.py` | 반대 방향 evidence span 추출 |
| `news/catalyst.py` | structured catalyst event 생성과 점수화 |
| `technical/indicators.py` | SMA, RSI, MACD, ATR, volume 지표 계산 |
| `technical/reaction.py` | abnormal return, volume z-score, gap reaction 계산 |
| `technical/structure.py` | 시장 구조, 지지/저항, 모멘텀 판정 |
| `technical/signals.py` | 트레이딩 셋업, 진입/손절/목표/손익비 산출 |
| `charts/render.py` | 주석 차트 pack 생성 |
| `reports/composer.py` | Markdown/PDF 리포트 생성 |
| `evaluation/event_level.py` | 날짜별 아카이브 기반 event/setup/news-quality 성능 평가 |
| `scripts/export_static_research_site.py` | key-free JSON과 HTML 아카이브 생성 |
| `docs/app.js` | Chart.js 기반 정적 대시보드 렌더링 |

## 8. 후보 점수 정의

후보 점수는 매수 추천이 아니라 감시 우선순위다.

```text
score =
  source_score
  + technical_score
  + setup_score
  + catalyst_score
  + move_score
  - chase_risk_penalty
```

### Source score

후보가 어떤 발굴 경로에서 나왔는지 반영한다.

- `growth_tech`
- `gainers`
- `undervalued_growth`
- `active`
- `kr_risers`
- `kr_volume`
- `kr_kospi_marketcap`
- `kr_kosdaq_marketcap`

### Technical score

가격 구조, 모멘텀, 거래량 상태를 반영한다.

- uptrend 여부
- range/transition 여부
- RSI 기반 momentum 상태
- 거래량 참여도

### Setup score

`technical/signals.py`가 계산한다.

셋업 라벨:

- `breakout_watch`: 거래량 동반 고점 돌파
- `pullback_watch`: 상승 추세 안의 눌림목
- `long_watch`: 추세와 모멘텀이 유지되는 감시 구간
- `avoid_chase`: 단기 과열/이격 과대
- `risk_watch`: 추세 훼손 또는 분산 위험
- `wait`: 근거 부족

계산 요소:

- SMA20/SMA50/SMA100 정렬
- 20일 고점 돌파
- 20일 저점 이탈
- 20일선 근처 눌림
- MACD histogram 개선
- 거래량 20일 평균 대비 배수
- RSI 과열/약세
- ATR 기반 진입/손절/목표 산출

### Catalyst score

`news/catalyst.py`가 생성한 event의 materiality, novelty, source quality, market reaction, priced-in penalty를 반영한다.

CatalystEvent 핵심 필드:

- event_type / event_subtype
- affected_driver
- direction / horizon
- entities
- metrics
- evidence_spans
- counter_evidence
- source_quality_score
- market_reaction_score
- priced_in_risk

## 9. 뉴스 직접성 정의

뉴스 직접성 필터는 오탐을 줄이기 위한 핵심 안전장치다.

핵심 catalyst 후보가 되려면 다음 조건을 만족해야 한다.

- 제목, 요약, 본문 중 최소 하나에서 기업명, 주요 alias, 또는 티커가 직접 확인되어야 한다.
- 한국 종목은 6자리 종목코드 또는 기업명을 우선 사용한다.
- 미국 종목은 티커, 기업명, 주요 기업명 phrase를 사용한다.
- `[그래픽]`, 시황, 인기검색, 가격비교 같은 저신호 제목은 제외한다.

예시:

- `현대차 하청노조 사용자성 판정...` -> 현대차 직접 관련
- `성과급 요구 확산...카카오 파업 가결` -> 현대차 catalyst에서 제외
- `The Spill: Apple...` -> WDC catalyst에서 제외

## 10. 정적 HTML 산출물

정적 리포트는 `docs/` 아래에 저장된다.

| 파일 | 역할 |
|---|---|
| `docs/index.html` | 정적 대시보드 shell |
| `docs/styles.css` | 모바일 친화 UI 스타일 |
| `docs/app.js` | 데이터 로딩, Chart.js 렌더링, 날짜 전환 |
| `docs/report-data.json` | 최신 리포트 데이터 |
| `docs/data/YYYY-MM-DD.json` | 날짜별 스냅샷 |
| `docs/data/index.json` | 사용 가능한 날짜 목록 |

대시보드 섹션:

- 날짜별 리서치 노트
- Market Pulse KPI
- 전일 예측 점검
- Focused chart
- Analyst memo
- 후보 테이블
- 테마 강도
- 뉴스 포착
- 리스크 체크포인트

## 11. Outcome 평가 정의

`scripts/export_static_research_site.py`는 전일 스냅샷이 있을 때 outcome을 계산한다.

비교 방식:

```text
previous snapshot candidate close
vs
current latest close
```

저장 필드:

- previousDate
- currentDate
- trackedCount
- withPriceCount
- positiveCount
- negativeCount
- averageReturn
- ticker별 previousRank, previousScore, previousClose, currentClose, nextReturn

주의:

- 이는 단순 익일 종가 비교다.
- benchmark/sector excess return은 아직 포함하지 않는다.
- 가격 데이터가 없는 후보는 pending 처리한다.

`research-copilot evaluate-events`는 `docs/data` 아카이브를 읽어 event-level 평가 CSV/JSON을 생성한다.

집계 축:

- event_type / event_subtype
- setup_action
- news_relevance_level

핵심 metric:

- measured_records
- hit_rate
- avg_next_return
- avg_catalyst_score

## 12. 보안 및 운영 원칙

- `.env`, `.env.*` raw secret은 커밋하지 않는다.
- 1Password를 사용할 때는 `.env.1password`에 `op://...` reference만 둔다.
- `docs/`에는 API key가 없는 key-free JSON만 저장한다.
- GitHub Pages는 public repo에서 배포된다.
- 리포트는 research-only이며 투자 자문이 아니다.
- broker/execution API는 연결하지 않는다.

## 13. 배포 정의

GitHub Pages 배포는 `.github/workflows/deploy-pages.yml`이 담당한다.

트리거:

- `main` push
- manual workflow dispatch

배포 대상:

```text
docs/
```

운영 URL:

```text
https://samgulza.github.io/equity-research-copilot/
```

## 14. 현재 한계

- 뉴스 clustering은 lightweight token embedding 기반이며 대형 embedding/reranker는 아직 붙이지 않았다.
- 회사명 직접성은 제목/요약/본문까지 보지만 기사 주체/문맥 완전 판별은 제한적이다.
- 한국 데이터는 Naver 기반이며 OpenDART/KRX 정식 adapter는 후속이다.
- chart setup은 rule-based이며 백테스트 기반 calibration이 아직 없다.
- outcome은 단순 다음날 가격 비교이고, market reaction은 현재 benchmark가 없으면 raw abnormal proxy를 사용한다.
- LLM analyst/critic prompt는 문서화되어 있으나 정적 HTML pipeline에는 아직 깊게 연결되지 않았다.

## 15. 후속 개발 우선순위

1. Sector-relative return과 benchmark 대비 outcome 추가
2. 대형 embedding/reranker 기반 catalyst clustering
3. 기사 주체 판별 강화
4. OpenDART/KRX adapter 추가
5. LLM/FinGPT-style extractor + critic을 report composition에 연결
6. source hallucination, priced-in error, event precision 평가 추가
7. PDF/HTML 리포트의 source appendix 강화
8. GitHub Actions Node 24 전환 경고 대응

## 16. 품질 기준

좋은 리포트는 다음 조건을 만족해야 한다.

- catalyst가 종목과 직접 관련된다.
- 뉴스가 business driver와 연결된다.
- 차트 구조와 뉴스가 따로 놀지 않는다.
- 이미 가격에 반영된 움직임은 chase risk로 감점한다.
- 진입보다 무효화 조건과 리스크를 먼저 보여준다.
- 전일 판단을 다음날 outcome으로 검증한다.

나쁜 리포트는 다음과 같다.

- 다른 회사 뉴스가 핵심 촉매로 올라온다.
- 좋은 뉴스가 많다는 이유만으로 후보 점수가 높다.
- RSI/MACD를 나열만 하고 셋업 판단과 연결하지 않는다.
- 급등 이후 추격 리스크를 무시한다.
- 출처와 날짜가 불분명하다.
