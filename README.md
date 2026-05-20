# OpenBB + OpenClaw Equity Research Copilot

뉴스 기반 종목 해석, 차트 주석, thesis memory, point-in-time 평가를 결합한 리서치 코파일럿 하네스입니다.

## 핵심 원칙

- OpenBB/Fincept가 이미 하는 데이터 터미널 기능은 재구현하지 않습니다.
- OpenBB는 price/fundamentals/economic/provider abstraction layer로 사용합니다.
- OpenClaw는 skill orchestration, report contract, critic/evaluation harness로만 사용합니다.
- LLM은 계산 엔진이 아니라 catalyst extraction, chart explanation, scenario reasoning, critic 역할만 수행합니다.
- 출력은 `상세 보고서 + annotated chart pack + catalyst timeline + evaluation record`입니다.

## 빠른 실행

```bash
python3.13 -m venv .venv
source .venv/bin/activate
uv pip install -e '.[openbb]'
research-copilot analyze NVDA --days 180 --format both --with-fundamentals
research-copilot analyze NVDA --days 180 --format both --with-fundamentals --with-news --include-sec
research-copilot discover --days 180 --news-days 7 --candidate-limit 25 --top 10 --analyze-top 3 --format md
research-copilot screen --watchlist config/watchlist.example.json --days 90 --top 4
research-copilot daily --watchlist config/watchlist.example.json --days 120 --top 2 --format md
research-copilot evaluate NVDA --start 2024-01-01 --horizon-days 20 --step-days 10 --lookback-days 120
python scripts/export_static_research_site.py
```

데모는 `examples/data/nvda_synthetic_ohlcv.csv`를 사용합니다. 이 fixture는 실제 NVDA 현재가/최근 고점 anchor를 반영해 **차트 주석 엔진을 시연**하기 위한 synthetic OHLCV입니다. 실제 운용에서는 `OpenBBAdapter`가 OpenBB OHLCV를 가져오도록 설정합니다.

## 실데이터 연결

```bash
uv pip install -e '.[openbb]'
```

OpenBB 호출은 반드시 `src/equity_research_copilot/adapters/openbb_adapter.py`에 격리합니다. OpenBB endpoint/provider mapping이 바뀌어도 나머지 분석/보고서 레이어는 normalized dataframe만 받게 둡니다.

## 현재 설치본

이 Mac에서는 외장 SSD에 설치합니다.

```bash
cd /Volumes/app/equity-research-copilot
source .venv/bin/activate
research-copilot analyze NVDA --days 180 --format both --with-fundamentals
```

1Password secret 주입이 필요한 provider/API를 쓸 때는 raw key를 파일에 쓰지 않고 `op://` reference를 사용합니다.

```bash
cp .env.1password.example .env.1password
# .env.1password에는 raw key가 아니라 op://... reference만 넣기
scripts/run_with_1password.sh research-copilot discover --universe all --candidate-limit 25 --top 10 --analyze-top 3
```

네이버 뉴스 검색 API를 쓰면 한국 종목의 뉴스 해석 품질이 올라갑니다.

```bash
export NAVER_CLIENT_ID="..."
export NAVER_CLIENT_SECRET="..."
research-copilot discover --universe kr --candidate-limit 20 --top 8 --analyze-top 2
```

실운용에서는 raw 값을 shell history나 파일에 남기지 말고 `.env.1password`에 `op://...` reference로 둡니다. `discover`는 CSV/Markdown과 함께 상위 후보 PDF도 `runs/discovery/`에 생성합니다.

생성물은 `runs/<TICKER>/` 아래에 저장됩니다.

- `reports/<TICKER>_research_memo.md`
- `reports/<TICKER>_research_memo.pdf`
- `charts/*_market_structure.png`
- `charts/*_momentum_volume.png`
- `charts/*_event_overlay.png`
- `data/*_ohlcv.csv`

## HTML 리서치 대시보드

GitHub Pages에 올려서 볼 수 있는 정적 리포트는 `docs/` 아래에 있습니다. API 키와 provider 호출은 로컬 Python 실행 단계에서만 쓰고, `docs/report-data.json`에는 리포트에 필요한 후보/뉴스/차트 데이터만 저장합니다.

```bash
cd /Volumes/app/equity-research-copilot
source .venv/bin/activate
python scripts/export_static_research_site.py --top 12
npx --yes http-server docs -p 4173 -a 127.0.0.1
```

브라우저에서 `http://127.0.0.1:4173`을 열면 Chart.js 기반 HTML 리포트를 확인할 수 있습니다. GitHub에 올린 뒤 Pages를 켜면 `.github/workflows/deploy-pages.yml`이 `docs/`를 배포합니다.

날짜별 누적은 `docs/data/`에 저장됩니다.

- `docs/report-data.json`: 최신 리포트
- `docs/data/YYYY-MM-DD.json`: 날짜별 스냅샷
- `docs/data/index.json`: HTML이 읽는 날짜 목록

매일 로컬에서 새 리포트를 쌓을 때는 아래 한 줄을 실행합니다. 이전 날짜 스냅샷이 있으면 HTML의 `전일 예측 점검` 섹션에서 전일 후보의 다음날 수익률을 자동 계산합니다.

```bash
scripts/run_daily_static_report.sh
```

현재 MVP에서 동작하는 범위:

- OpenBB `yfinance` 기반 미국 주식 OHLCV 수집
- OpenBB fundamentals snapshot 시도
- OpenBB company news 수집
- Naver Search News API 기반 한국 종목 뉴스 수집
- SEC EDGAR filing 수집
- catalyst dedup/scoring 및 JSON export
- market movers / growth / undervalued-growth / active discovery 기반 동적 후보 발굴
- 종목 후보별 뉴스 방향성/주요 기사/뉴스 해석 block 생성
- technical structure / support / resistance / RSI / MACD / volume 해석
- AI-Trader식 operation 신호를 참고한 트레이딩 셋업 점수, 진입/손절/목표/손익비 산출
- annotated chart pack 3장 생성
- Markdown/PDF deep-dive report 생성
- watchlist screening CSV 생성
- thesis memory JSONL 저장/조회
- daily watchlist run 생성
- point-in-time OHLCV evaluation CSV/summary 생성

아직 Phase 1 후속으로 남은 범위:

- RSS/GDELT/licensed news provider 추가
- 더 정교한 event clustering/deduplication
- sector-relative return / benchmark 비교
- LLM analyst + critic prompt를 live report composition에 연결
- evaluation metric 확장: Top-K excess return, hallucinated source rate, priced-in error rate

## 주요 파일

| 파일 | 용도 |
|---|---|
| `ABC_DELIVERABLES.md` | A/B/C 산출물 요약과 파일 맵 |
| `PRD.md` | 제품 요구사항과 리포트 품질 기준 |
| `SYSTEM_ARCHITECTURE.md` | 데이터/에이전트/평가 아키텍처 |
| `CODE_ARCHITECTURE.md` | Python 모듈 구조와 확장 지점 |
| `openclaw/SKILL.md` | OpenClaw skill contract |
| `examples/reports/NVDA_sample_report.md` | 샘플 리서치 리포트 |
| `examples/reports/NVDA_sample_report_polished.pdf` | 주석 차트 포함 PDF 샘플 리포트 |
| `examples/charts/*.png` | 주석 차트 예시 |
| `schemas/*.json` | LLM 출력 검증용 JSON schema |

## 리포트 계약

각 리포트는 최소 다음을 포함합니다.

1. Verdict/confidence
2. Technical market structure
3. Annotated chart pack
4. News/catalyst cards
5. Priced-in assessment
6. Bull/base/bear scenario table
7. Invalidation levels
8. Counter-thesis / critic memo
9. Source appendix
10. Research-only disclaimer
