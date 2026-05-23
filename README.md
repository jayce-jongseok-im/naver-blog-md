# naver-blog-md

네이버 블로그를 마크다운(.md) 파일로 백업하는 작은 Python 도구입니다.

본인이 쓴 글이 네이버 안에만 갇혀 있는 게 불안할 때, 다른 곳으로 옮기거나 LLM에게 학습/요약시킬 마크다운 사본을 만들고 싶을 때 쓰세요.

## 특징

- 글 한 편마다 `.md` 파일 1개. 파일명에 날짜·제목·log_no 포함.
- 프론트매터(`title`, `log_no`, `date`, `category_no`, `source` URL)가 자동으로 들어가서 Obsidian·Logseq·기타 위키 도구에 바로 ingest 가능.
- 카테고리 분포 스캔 → 특정 카테고리만 받기 / 제외하기 옵션.
- 이어받기 지원 (`--skip-existing`).
- 외부 의존성 3개 (`requests`, `beautifulsoup4`, `markdownify`)만.

## 설치

```bash
git clone https://github.com/<YOUR_GITHUB>/naver-blog-md.git
cd naver-blog-md
pip install -r requirements.txt
```

Python 3.10 이상 권장.

## 빠른 시작

블로그 ID 확인: 본인 블로그가 `https://blog.naver.com/mynaverid` 라면 ID는 `mynaverid`.

### 1. 먼저 카테고리 분포만 확인

```bash
python naver_blog_md.py mynaverid --scan-only
```

출력 예시:
```
[category 9] 93편
  - 2026. 4. 7.  중용
  - 2026. 3. 5.  꾸준함, 그 너머
  ...

[category 10] 71편
  - 2026. 5. 13.  복잡
  - 2026. 5. 2.  바이브 코딩
  ...
```

→ 카테고리 번호와 어떤 글들이 들어있는지 보고 본인이 식별.

### 2. 전체 받기

```bash
python naver_blog_md.py mynaverid
```

`./posts/` 폴더에 모든 글이 마크다운으로 저장됩니다.

### 3. 특정 카테고리만 / 제외

```bash
# 카테고리 9와 10만 받기
python naver_blog_md.py mynaverid --category 9,10

# 카테고리 7과 18은 제외
python naver_blog_md.py mynaverid --exclude-category 7,18
```

### 4. 이어받기

중간에 끊기면 같은 명령에 `--skip-existing` 추가:

```bash
python naver_blog_md.py mynaverid --skip-existing
```

이미 저장된 글(파일명의 `log_no` 매칭)은 건너뜁니다.

## 옵션 전체 목록

```
positional:
  blog_id              blog.naver.com/<ID>의 ID

options:
  --out OUT            저장 폴더 (기본: ./posts)
  --limit N            최대 N편만 (0=전체)
  --delay SEC          글 사이 대기 초 (기본 0.8)
  --skip-existing      이미 저장된 글 건너뛰기
  --scan-only          본문 다운로드 없이 카테고리 분포만 출력
  --category C1,C2     특정 카테고리만 받기
  --exclude-category   특정 카테고리 제외
  --version            버전 출력
```

## 저장 형식

파일명 예: `20260513_복잡_224283765316.md`

내용:
```markdown
---
title: 복잡
log_no: 224283765316
date: 2026. 5. 13.
category_no: 10
source: https://blog.naver.com/mynaverid/224283765316
---

# 복잡

머리 속이 단어 하나로 복잡하다
```

## 어떻게 동작하나요

1. **글 목록 수집**: `blog.naver.com/PostTitleListAsync.naver` 비공식 API로 페이지네이션 (한 페이지 30편).
2. **본문 수집**: 모바일 페이지 `m.blog.naver.com/{id}/{log_no}` 에서 SmartEditor 본문 (`.se-main-container`) 추출.
3. **마크다운 변환**: `markdownify` 라이브러리로 HTML → MD 변환.

이미지는 원본 URL 그대로 마크다운 이미지 링크로 들어갑니다 (다운로드는 안 함).

## 주의 사항

- **본인 블로그 백업 용도입니다.** 타인의 블로그를 무단으로 대량 수집하지 마세요. 저작권·이용약관 문제가 됩니다.
- **비공식 API를 사용합니다.** 네이버가 API를 바꾸면 동작이 깨질 수 있습니다. 깨졌을 때 이슈로 알려주시면 고치겠습니다.
- **요청 간격(`--delay`)을 너무 짧게 두지 마세요.** 기본 0.8초가 권장값입니다. 차단될 수 있습니다.
- **비공개 글·이웃공개 글은 받아지지 않을 수 있습니다.** 비공개 글의 처리는 보장하지 않습니다.

## 제한

- 댓글은 가져오지 않습니다.
- 이미지를 로컬로 다운로드하지 않습니다 (URL만 보존).
- 동영상 첨부는 링크로만 남습니다.
- 동시 요청 안 함 (의도적으로 단일 스레드).

## 라이선스

MIT License. 자유롭게 쓰고, 고치고, 배포하세요. 자세한 내용은 [LICENSE](LICENSE) 파일 참고.

## 기여

버그·개선 제안은 GitHub Issues 또는 Pull Request로 환영합니다.
