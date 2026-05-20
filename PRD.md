# PRD - News + Technical Equity Research Copilot

## 1. 제품 정의

이 제품은 단순 뉴스 요약기나 자동매매 봇이 아니다. 목표는 다음이다.

> 공개 뉴스/공시/가격 데이터를 구조화하고, 차트분석론 기반 주석 차트와 함께 종목별 상승/하락 thesis, catalyst, invalidation level, scenario를 생성하는 리서치 코파일럿.

## 2. 대상 사용자

- 개인/기관 리서치 보조 사용자
- 주식 watchlist를 매일 점검하고 싶은 사용자
- 뉴스와 차트를 별도로 보지 않고 한 리포트에서 결합 해석을 원하는 사용자
- 매매 실행이 아니라 판단 보조/리서치 기록/평가를 원하는 사용자

## 3. 핵심 사용 시나리오

### 3.1 단일 종목 deep-dive

입력:

```text
analyze NVDA --horizon 20d --report deep --charts annotated
```

출력:

- Executive summary
- Technical structure memo
- Annotated chart pack
- News/catalyst table
- Priced-in assessment
- Bull/base/bear scenarios
- Watchpoints
- Critic review

### 3.2 Watchlist screening

입력:

```text
screen --watchlist config/watchlist.example.json --days 7
```

출력:

- 상위 bullish setup
- 상위 bearish risk
- catalyst novelty ranking
- 기술적 전환 후보
- no-edge 종목 제외 사유

### 3.3 Daily update

입력:

```text
daily --watchlist core_ai_semis --since yesterday
```

출력:

- 전일 thesis 대비 변화
- 새 catalyst
- 가격 반응
- alert-worthy level

## 4. 비기능 요구사항

| 항목 | 요구사항 |
|---|---|
| 재현성 | 모든 리포트는 data snapshot timestamp, provider, source URL을 남긴다. |
| 안전성 | 매수/매도 실행, broker API, position sizing 자동화 금지. |
| 검증성 | LLM 출력은 JSON schema로 검증한다. |
| 설명가능성 | 차트 판단은 지표값이 아니라 `왜 그렇게 보는지`를 문장과 주석으로 설명한다. |
| 평가가능성 | point-in-time backtest가 가능해야 한다. |
| 모델 독립성 | OpenAI/Anthropic/local LLM을 교체 가능하게 둔다. |

## 5. 리포트 품질 기준

### 5.1 좋은 보고서의 기준

- 뉴스 headline sentiment가 아니라 business driver에 연결한다.
- 차트는 지표 나열이 아니라 market structure를 먼저 설명한다.
- 가격에 이미 반영됐는지 평가한다.
- 반대 근거와 무효화 조건을 명시한다.
- 확률/신뢰도와 time horizon을 분리한다.

### 5.2 나쁜 보고서의 패턴

- "AI 수요가 강하므로 상승 가능" 같은 generic 문장
- RSI/MACD/MA를 나열만 하고 결론과 연결하지 않음
- 좋은 뉴스가 많다는 이유만으로 bullish 판단
- 기사 중복을 독립 catalyst로 오판
- 이미 급등한 가격 반응을 무시

## 6. MVP 범위

### Phase 1

- 미국 주식 watchlist
- OpenBB 가격/펀더멘털 adapter
- RSS/GDELT/SEC/news adapter
- daily/weekly 차트 주석 3장
- ticker deep report
- analyst + critic prompt

### Phase 2

- 한국 주식: OpenDART, KRX, Naver News adapter
- thesis memory
- event clustering/deduplication
- sector-relative return
- event overlay chart

### Phase 3

- point-in-time evaluation harness
- confidence calibration
- Top-K watchlist performance
- alert archive
- dashboard/Fincept/OpenBB Workspace integration

## 7. 산출물 계약

각 종목 리포트는 최소 다음을 포함해야 한다.

```text
1. Verdict
2. Technical structure
3. Chart annotations
4. News/catalyst cards
5. Priced-in analysis
6. Scenario table
7. Invalidation levels
8. Risks and counter-thesis
9. Watchpoints
10. Data/source appendix
```
