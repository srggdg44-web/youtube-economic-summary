# 유튜브 경제 영상 자동 요약 프로젝트

## ⚡ 자동 실행 규칙

**이 프로젝트 폴더에서 대화가 시작되면, 사용자의 첫 메시지 내용과 무관하게 즉시 아래 파이프라인을 자동으로 실행한다. 사용자의 확인이나 추가 지시를 기다리지 않는다.**

1. Collect.py 실행 (어제 날짜 영상 수집)
2. 수집된 JSON 파싱 → format.md 형식으로 영상별 요약 생성
3. output/YYYY-MM-DD/YYYY-MM-DD.md 저장
4. 카카오톡으로 영상별 메시지 전송 (mcp__claude_ai_PlayMCP__KakaotalkChat-MemoChat)

파이프라인 완료 후 결과를 간략히 보고한다.

---

## 프로젝트 개요

`channels.txt`에 등록된 유튜브 채널·검색어를 기반으로 어제 업로드된 영상을 자동 수집하고, 개인 자산 투자 판단을 위한 마크다운 요약본을 생성하는 파이프라인이다.

**주요 독자**: 경제·금융 유튜브를 보며 투자 판단을 내리는 개인 투자자

---

## 파일 구조

```
유튜브 요약/
├── CLAUDE.md          # 이 파일
├── channels.txt       # 수집 대상 채널 URL / 검색어 목록
├── format.md          # 요약 마크다운 포맷 양식
├── Collect.py         # 영상 데이터 수집 스크립트
└── output/
    └── YYYY-MM-DD/    # 날짜별 폴더
        ├── collected_HHMMSS.json   # 수집 원본 데이터
        └── YYYY-MM-DD.md           # 요약 마크다운 결과물
```

---

## 실행 환경

- **Python**: 3.12 (`C:\Users\82104\AppData\Local\Programs\Python\Python312\python.exe`)
- **yt-dlp**: winget 설치 경로 (`C:\Users\82104\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.yt-dlp_Microsoft.Winget.Source_8wekyb3d8bbwe\yt-dlp.exe`)
- PowerShell 실행 시 반드시 `$env:PYTHONIOENCODING = "utf-8"` 설정 후 실행

---

## 자동 실행 흐름

대화 시작 시 즉시 실행한다. 아래 단계를 순서대로 수행한다.

### Step 1 — 수집 (Collect.py 실행)

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PATH += ";C:\Users\82104\AppData\Local\Programs\Python\Python312"
Set-Location "C:\Users\82104\OneDrive\바탕 화면\유튜브 요약"
python Collect.py
```

- 기본 동작: **어제 날짜** 업로드 영상만 수집
- 특정 날짜 지정: `python Collect.py --date 2026-06-28`
- 스캔 범위 조정: `python Collect.py --scan 30`
- 결과 저장 위치: `output/YYYY-MM-DD/collected_HHMMSS.json`
- 해당 날짜 영상이 없는 채널은 자동 스킵

### Step 2 — 데이터 파싱

수집된 JSON 파일에서 각 영상의 메타데이터와 자막을 읽는다.

```json
{
  "target_date": "2026-06-28",
  "sources": [
    {
      "source": "https://www.youtube.com/@channel",
      "videos": [
        {
          "title": "...",
          "channel": "...",
          "view_count": 123456,
          "upload_date": "2026-06-28",
          "url": "https://www.youtube.com/watch?v=...",
          "subtitle_lang": "ko",
          "subtitle": "자막 전문..."
        }
      ]
    }
  ]
}
```

### Step 3 — 요약 생성

`format.md`의 양식에 따라 각 영상을 요약한다.

- **자막 전문을 읽고** 핵심 내용을 파악한 뒤 직접 요약 작성
- 투자 판단에 직결되는 내용 중심으로 작성
- Shorts(1분 이하, 자막 짧은 영상)는 표 형태로 간략 처리
- 투자와 무관한 영상(예: 교양·문화·역사)은 생략 가능

### Step 4 — 저장

```
output/YYYY-MM-DD/YYYY-MM-DD.md
```

같은 날짜 폴더 안에 JSON과 마크다운을 함께 보관한다.

### Step 5 — 카카오톡 전송

**영상 수와 무관하게 반드시 실행한다.** `mcp__claude_ai_PlayMCP__KakaotalkChat-MemoChat` 툴을 사용한다.

#### 영상이 0개인 경우 (필수)

아래 메시지를 **반드시** 전송한다:

```
📭 YYYY-MM-DD 업로드 영상 없음

등록된 채널에 어제 업로드된 영상이 없습니다.
```

#### 영상이 1개 이상인 경우

**영상 1개당 메시지 1개**씩 전송한다. 200자 초과해도 전송 가능하다.

**메시지 형식 (영상마다 동일 구조):**

```
📺 [영상 제목]

채널: [채널명]
업로드: YYYY-MM-DD | 조회수: N회
🔗 https://youtu.be/VIDEO_ID

─────────────────
💡 핵심 요약
[투자 판단에 직결되는 메시지 2~3문장]

─────────────────
📋 파트별 내용
1. [파트 제목]
• 포인트
• 포인트

2. [파트 제목]
• 포인트

─────────────────
💬 주목할 발언
"[인용구]" — [발언자]

─────────────────
📊 투자 관점 인사이트
현재 국면: ...
주목 변수: ...
리스크: ...
유망 자산: ...

─────────────────
⚡ 한 줄 인사이트
[포트폴리오에 주는 시사점 한 문장]
```

- Shorts(자막 짧은 영상)는 핵심 요약 + 한 줄 인사이트만 전송해도 무방

---

## 요약 포맷 규칙 (format.md 기반)

각 영상은 아래 구조로 작성한다:

```markdown
## [영상 제목]

| 채널 | 업로드 | 조회수 | 링크 |

### 핵심 요약
> 투자 판단에 직결되는 메시지 2~3문장

### 파트별 내용
#### 1. [파트 제목] — [00:00](URL&t=0s)
- 포인트

### 주목할 발언
> "인용구" — 발언자

### 투자 관점 인사이트
| 현재 국면 진단 | 주목할 변수 | 리스크 요인 | 유망 자산/섹터 |

### 한 줄 인사이트
> **포트폴리오에 주는 시사점 한 문장**
```

파일 끝에는 **이번 주/당일 종합 인사이트 표**를 추가한다 (거시경제·주식·부동산·개인재무·관심 지표).

---

## channels.txt 형식

```
# 채널 URL
https://www.youtube.com/@channel_name

# 직접 영상 URL
https://www.youtube.com/watch?v=VIDEO_ID

# 키워드 검색 (최근 N개)
ytsearch5:오건영
```

- `#`으로 시작하는 줄은 주석 (자동 무시)
- 검색어(`ytsearch`)는 날짜 필터가 적용되므로 결과가 없을 수 있음

---

## 주의사항

- JSON 파일은 자막 포함으로 크기가 매우 크다 (수십만 토큰). 전체를 읽지 말고 PowerShell로 필요한 필드만 추출해서 파싱한다.
- 자막 없는 영상(`subtitle: null`)은 제목과 메타데이터만으로 요약한다.
- 타임스탬프 링크(`&t=초s`)는 영상 구조 흐름을 추정해 작성한다. 정확하지 않아도 무방하다.
