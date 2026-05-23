"""
naver-blog-md
=============

네이버 블로그를 마크다운(.md) 파일로 통째로 백업해주는 작은 도구입니다.

사용법:
    python naver_blog_md.py BLOG_ID                  # 전체 글 받기
    python naver_blog_md.py BLOG_ID --scan-only      # 카테고리 분포만 확인
    python naver_blog_md.py BLOG_ID --category 10,5  # 특정 카테고리만
    python naver_blog_md.py BLOG_ID --exclude-category 7,18  # 제외
    python naver_blog_md.py BLOG_ID --skip-existing  # 이어받기
    python naver_blog_md.py BLOG_ID --limit 10       # 최근 N편만

예시:
    python naver_blog_md.py mynaverid --out ./posts --delay 0.8

주의:
    - 본인 블로그 백업 용도입니다. 타인의 블로그를 무단으로 대량 수집하지 마세요.
    - 비공식 API를 사용하므로 네이버 변경에 따라 동작이 깨질 수 있습니다.
    - 요청 간격(--delay)을 너무 짧게 두면 차단될 수 있습니다 (기본 0.8초 권장).

License: MIT
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

__version__ = "0.1.0"

# 윈도우 콘솔 인코딩 대응
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

DESKTOP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}

MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
}

LIST_URL = "https://blog.naver.com/PostTitleListAsync.naver"
POST_URL_MOBILE = "https://m.blog.naver.com/{blog_id}/{log_no}"


def fetch_post_list(blog_id: str) -> list[dict]:
    """블로그의 모든 글 메타데이터를 페이지네이션 돌면서 수집한다."""
    posts: list[dict] = []
    page = 1
    headers = {**DESKTOP_HEADERS, "Referer": f"https://blog.naver.com/{blog_id}"}

    while True:
        params = {
            "blogId": blog_id,
            "currentPage": page,
            "countPerPage": 30,
        }
        r = requests.get(LIST_URL, params=params, headers=headers, timeout=15)
        r.raise_for_status()

        # 네이버 응답이 가끔 invalid escape를 포함 → 백슬래시 정규화 후 파싱
        text = r.text
        text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)
        try:
            data = json.loads(text, strict=False)
        except json.JSONDecodeError as e:
            print(f"  [list] page {page} JSON 파싱 실패: {e}")
            break

        post_list = data.get("postList", [])
        if not post_list:
            break

        for p in post_list:
            posts.append(
                {
                    "log_no": p["logNo"],
                    "title": urllib.parse.unquote(p["title"]),
                    "add_date": p.get("addDate", ""),
                    "category_no": p.get("categoryNo", ""),
                    "parent_category_no": p.get("parentCategoryNo", ""),
                }
            )

        print(f"  [list] page {page}: +{len(post_list)} (total {len(posts)})")

        total_count = int(data.get("totalCount", 0))
        if len(posts) >= total_count or len(post_list) < 30:
            break
        page += 1
        time.sleep(0.3)

    return posts


def fetch_post(blog_id: str, log_no: str) -> tuple[str, str] | None:
    """글 한 편을 모바일 페이지에서 가져와서 (제목, 본문 HTML) 반환."""
    url = POST_URL_MOBILE.format(blog_id=blog_id, log_no=log_no)
    r = requests.get(url, headers=MOBILE_HEADERS, timeout=15)
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # 제목 후보 (SmartEditor One vs 구버전 vs 매우 구버전)
    title_el = (
        soup.select_one(".se-title-text")
        or soup.select_one(".se_title")
        or soup.select_one("h3.tit_h3")
        or soup.select_one("h3.se_textarea")
    )
    title = title_el.get_text(strip=True) if title_el else ""

    # 본문 후보
    content_el = (
        soup.select_one(".se-main-container")
        or soup.select_one(".se_component_wrap")
        or soup.select_one("#postViewArea")
    )
    if content_el is None:
        return None

    return title, str(content_el)


def safe_filename(s: str, max_len: int = 80) -> str:
    """파일명으로 쓸 수 있게 위험한 문자 제거."""
    s = re.sub(r'[\\/:*?"<>|]', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len] or "untitled"


def pad_date(raw_date: str) -> str:
    """네이버의 '2026. 5. 13.' 형식을 '20260513' YYYYMMDD로 변환."""
    parts = [p.strip() for p in raw_date.split(".") if p.strip()]
    if len(parts) < 3:
        return "unknown"
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{y:04d}{m:02d}{d:02d}"
    except ValueError:
        return "unknown"


def save_post(out_dir: Path, blog_id: str, post: dict, title: str, html: str) -> Path:
    """글을 마크다운으로 변환해 저장. 프론트매터 포함."""
    body_md = md(html, heading_style="ATX", bullets="-")
    body_md = re.sub(r"\n{3,}", "\n\n", body_md).strip()

    # 파일명: YYYYMMDD_제목_logNo.md
    date_part = pad_date(post["add_date"])
    fname = f"{date_part}_{safe_filename(title or post['title'])}_{post['log_no']}.md"
    fpath = out_dir / fname

    # 프론트매터 + 본문
    title_safe = (title or post["title"]).replace("\n", " ").strip()
    front = (
        f"---\n"
        f"title: {title_safe}\n"
        f"log_no: {post['log_no']}\n"
        f"date: {post['add_date']}\n"
        f"category_no: {post['category_no']}\n"
        f"source: https://blog.naver.com/{blog_id}/{post['log_no']}\n"
        f"---\n\n"
        f"# {title_safe}\n\n"
    )

    fpath.write_text(front + body_md + "\n", encoding="utf-8")
    return fpath


def show_category_breakdown(posts: list[dict]) -> None:
    """카테고리 번호별로 글 수와 샘플 제목을 보여줘서 사용자가 식별할 수 있게."""
    from collections import defaultdict

    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in posts:
        key = (
            p.get("parent_category_no") or p.get("category_no") or "",
            p.get("category_no") or "",
        )
        buckets[key].append(p)

    print(f"\n=== 카테고리 분포 (총 {len(posts)}편) ===")
    for key in sorted(buckets.keys(), key=lambda k: (k[0], k[1])):
        parent, cat = key
        items = buckets[key]
        marker = f"category {cat}"
        if parent and parent != cat:
            marker += f" (상위 {parent})"
        print(f"\n[{marker}] {len(items)}편")
        for p in items[:5]:
            print(f"  - {p['add_date']}  {p['title'][:60]}")
        if len(items) > 5:
            print(f"  ... 외 {len(items)-5}편")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="네이버 블로그를 마크다운으로 백업합니다.",
        epilog="자세한 옵션은 README.md를 참고하세요.",
    )
    ap.add_argument(
        "blog_id",
        help="네이버 블로그 ID. blog.naver.com/<ID> 의 <ID> 부분을 그대로 입력하세요.",
    )
    ap.add_argument("--out", default="./posts", help="저장 폴더 (기본: ./posts)")
    ap.add_argument("--limit", type=int, default=0, help="최대 N편만 (0=전체)")
    ap.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="글 사이 대기 초. 너무 짧으면 차단될 수 있음 (기본 0.8)",
    )
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="이미 저장된 글(파일명에 log_no 매칭)은 건너뛰기. 이어받기에 유용.",
    )
    ap.add_argument(
        "--scan-only",
        action="store_true",
        help="본문 다운로드 없이 카테고리 분포만 출력하고 종료",
    )
    ap.add_argument(
        "--category",
        type=str,
        default="",
        help="특정 카테고리 번호만 받기 (콤마 구분, 예: --category 10,5)",
    )
    ap.add_argument(
        "--exclude-category",
        type=str,
        default="",
        help="특정 카테고리 번호 제외 (콤마 구분, 예: --exclude-category 7,18)",
    )
    ap.add_argument("--version", action="version", version=f"naver-blog-md {__version__}")
    args = ap.parse_args()

    out_dir = Path(args.out)
    if not args.scan_only:
        out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/2] 글 목록 가져오는 중... (blog_id={args.blog_id})")
    try:
        posts = fetch_post_list(args.blog_id)
    except requests.RequestException as e:
        print(f"FAIL: 글 목록 가져오기 실패: {e}")
        return 1

    print(f"  총 {len(posts)}편 발견")

    if not posts:
        print("저장할 글이 없습니다. blog_id가 정확한지 확인하세요.")
        return 0

    if args.scan_only:
        show_category_breakdown(posts)
        return 0

    if args.category:
        wanted = {c.strip() for c in args.category.split(",") if c.strip()}
        before = len(posts)
        posts = [
            p
            for p in posts
            if (p.get("category_no") or "") in wanted
            or (p.get("parent_category_no") or "") in wanted
        ]
        print(f"  --category {args.category} 적용 → {before} → {len(posts)}편")

    if args.exclude_category:
        excluded = {c.strip() for c in args.exclude_category.split(",") if c.strip()}
        before = len(posts)
        posts = [
            p
            for p in posts
            if (p.get("category_no") or "") not in excluded
            and (p.get("parent_category_no") or "") not in excluded
        ]
        print(
            f"  --exclude-category {args.exclude_category} 적용 → {before} → {len(posts)}편"
        )

    if args.limit:
        posts = posts[: args.limit]
        print(f"  --limit {args.limit} 적용 → {len(posts)}편만 받음")

    print(f"\n[2/2] 글 본문 가져오는 중... (delay={args.delay}s)")
    saved = 0
    failed: list[tuple[str, str]] = []
    skipped = 0

    existing: set[str] = set()
    if args.skip_existing:
        for p in out_dir.glob("*.md"):
            # 파일명 끝의 _{log_no}.md 추출
            m = re.search(r"_(\d+)\.md$", p.name)
            if m:
                existing.add(m.group(1))

    for i, post in enumerate(posts, 1):
        if post["log_no"] in existing:
            skipped += 1
            print(f"  [{i}/{len(posts)}] SKIP (already): {post['title']}")
            continue

        try:
            result = fetch_post(args.blog_id, post["log_no"])
            if result is None:
                failed.append((post["log_no"], "본문 없음"))
                print(f"  [{i}/{len(posts)}] FAIL (no body): {post['title']}")
                continue
            title, html = result
            fpath = save_post(out_dir, args.blog_id, post, title, html)
            saved += 1
            print(f"  [{i}/{len(posts)}] OK: {fpath.name}")
        except Exception as e:
            failed.append((post["log_no"], str(e)))
            print(f"  [{i}/{len(posts)}] FAIL: {post['title']} - {e}")

        time.sleep(args.delay)

    print(f"\n완료. 저장 {saved}편 / 건너뛰기 {skipped}편 / 실패 {len(failed)}편")
    if failed:
        print("실패 목록:")
        for log_no, err in failed:
            print(f"  - {log_no}: {err}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
