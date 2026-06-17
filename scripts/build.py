#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import html
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
ASSETS = ROOT / "assets"


SITE = {
    "name": "Fiona You WANG",
    "tagline": "Curator | Transdisciplinary Researcher | Artist",
    "description": (
        "Portfolio and research archive of Fiona You WANG, working across "
        "cosmotechnics, computational media, Space Art, curatorial studies, "
        "and digital wellbeing."
    ),
    "base_url": "",
}


@dataclass
class Page:
    source: Path | None
    title: str
    slug: str
    html: str
    summary: str
    image: str | None
    kind: str = "Page"
    updated: str = ""
    raw: str = ""


@dataclass
class OutlineNode:
    type: str
    title: str
    level: int = 0
    page: Page | None = None
    children: list["OutlineNode"] = field(default_factory=list)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    asciiish = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = asciiish.lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if lowered:
        return lowered
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"page-{digest}"


def clean_title(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    return value


def display_text(value: str) -> str:
    value = clean_title(value)
    value = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), value)
    value = re.sub(r"[*_`]+", "", value)
    return clean_title(value)


def split_obsidian_alt(value: str) -> tuple[str, str | None]:
    if "|" not in value:
        return value.strip(), None
    alt, size = value.rsplit("|", 1)
    if size.strip().isdigit():
        return alt.strip(), size.strip()
    return value.strip(), None


def youtube_id(url: str) -> str | None:
    patterns = [
        r"youtu\.be/([A-Za-z0-9_-]{6,})",
        r"youtube\.com/watch\?v=([A-Za-z0-9_-]{6,})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{6,})",
    ]
    for pattern in patterns:
        found = re.search(pattern, url)
        if found:
            return found.group(1)
    return None


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]*:contentReference\[[^\]]+\]\{[^}]+\}", "", text)
    # Some source notes place a heading immediately after an image.
    text = re.sub(r"(\]\([^)]+\))(?=#)", r"\1\n", text)
    return text


def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :]
    return text


def first_heading_or_stem(path: Path, text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return display_text(match.group(1))
    return display_text(path.stem)


def strip_markdown(value: str) -> str:
    value = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), value)
    value = re.sub(r"[*_`>#-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def summarize(text: str) -> str:
    body = strip_frontmatter(text)
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("!") or stripped == "---":
            continue
        summary = strip_markdown(stripped)
        if summary:
            return summary[:230] + ("..." if len(summary) > 230 else "")
    return ""


def first_image(text: str) -> str | None:
    match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", text)
    if match:
        url = match.group(1).strip()
        if not youtube_id(url):
            return url
    return None


def inline_html(text: str, page_lookup: dict[str, Page], prefix: str = "") -> str:
    placeholders: list[str] = []

    def stash(value: str) -> str:
        placeholders.append(value)
        return f"\u0000{len(placeholders) - 1}\u0000"

    def image_repl(match: re.Match[str]) -> str:
        raw_alt, url = match.group(1), match.group(2).strip()
        alt, width = split_obsidian_alt(raw_alt)
        video = youtube_id(url)
        if video:
            return stash(render_youtube(video, alt or "Video"))
        attrs = [
            f'src="{html.escape(url, quote=True)}"',
            f'alt="{html.escape(alt, quote=True)}"',
            'loading="lazy"',
        ]
        if width:
            attrs.append(f'width="{html.escape(width, quote=True)}"')
        return stash(f"<img {' '.join(attrs)}>")

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", image_repl, text)
    escaped = html.escape(text)

    def wiki_repl(match: re.Match[str]) -> str:
        target = clean_title(html.unescape(match.group(1)))
        label = clean_title(html.unescape(match.group(2) or match.group(1)))
        page = page_lookup.get(target)
        if not page:
            return f'<span class="text-reference">{html.escape(label)}</span>'
        return f'<a href="{page_href(page, prefix)}">{html.escape(label)}</a>'

    escaped = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", wiki_repl, escaped)

    def link_repl(match: re.Match[str]) -> str:
        label = match.group(1)
        url = html.unescape(match.group(2)).strip()
        if url.startswith(("http://", "https://")):
            extra = ' target="_blank" rel="noopener noreferrer"'
        else:
            extra = ""
        return f'<a href="{html.escape(url, quote=True)}"{extra}>{label}</a>'

    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)

    for index, value in enumerate(placeholders):
        escaped = escaped.replace(f"\u0000{index}\u0000", value)
    return escaped


def render_youtube(video_id: str, title: str = "Video") -> str:
    safe_id = html.escape(video_id, quote=True)
    safe_title = html.escape(title or "Video", quote=True)
    return (
        '<figure class="video-embed">'
        f'<iframe src="https://www.youtube.com/embed/{safe_id}?rel=0&modestbranding=1&playsinline=1" '
        f'title="{safe_title}" loading="lazy" allowfullscreen '
        'referrerpolicy="strict-origin-when-cross-origin" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share">'
        "</iframe>"
        "</figure>"
    )


def markdown_to_html(text: str, page_lookup: dict[str, Page], title: str, prefix: str = "") -> str:
    lines = strip_frontmatter(text).splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    open_list: str | None = None
    skip_first_h1 = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            joined = " ".join(item.strip() for item in paragraph if item.strip())
            blocks.append(f"<p>{inline_html(joined, page_lookup, prefix)}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal open_list
        if open_list:
            blocks.append(f"</{open_list}>")
            open_list = None

    def ensure_list(tag: str) -> None:
        nonlocal open_list
        if open_list != tag:
            close_list()
            blocks.append(f"<{tag}>")
            open_list = tag

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            close_list()
            continue

        if open_list and raw_line[:1].isspace() and blocks and blocks[-1].startswith("<li>"):
            continuation = inline_html(stripped, page_lookup, prefix)
            blocks[-1] = blocks[-1][:-5] + f"<br>{continuation}</li>"
            continue

        if stripped == "---":
            flush_paragraph()
            close_list()
            blocks.append("<hr>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            text_value = clean_title(heading.group(2))
            if level == 1 and not skip_first_h1 and text_value == title:
                skip_first_h1 = True
                continue
            skip_first_h1 = True
            level = min(level + 1, 6)
            anchor = slugify(text_value)
            blocks.append(
                f'<h{level} id="{anchor}">{inline_html(text_value, page_lookup, prefix)}</h{level}>'
            )
            continue

        image = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image:
            flush_paragraph()
            close_list()
            raw_alt, url = image.group(1), image.group(2).strip()
            alt, width = split_obsidian_alt(raw_alt)
            video = youtube_id(url)
            if video:
                blocks.append(render_youtube(video, alt or "Video"))
            else:
                style = f' style="max-width:{int(width)}px"' if width else ""
                blocks.append(
                    '<figure class="media">'
                    f'<img src="{html.escape(url, quote=True)}" alt="{html.escape(alt, quote=True)}" loading="lazy"{style}>'
                    "</figure>"
                )
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet:
            flush_paragraph()
            ensure_list("ul")
            blocks.append(f"<li>{inline_html(bullet.group(1), page_lookup, prefix)}</li>")
            continue

        numbered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if numbered:
            flush_paragraph()
            ensure_list("ol")
            blocks.append(f"<li>{inline_html(numbered.group(1), page_lookup, prefix)}</li>")
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            close_list()
            quote = stripped.lstrip("> ")
            blocks.append(f"<blockquote>{inline_html(quote, page_lookup, prefix)}</blockquote>")
            continue

        paragraph.append(stripped)

    flush_paragraph()
    close_list()
    return "\n".join(blocks)


def page_href(page: Page, prefix: str = "") -> str:
    return f"{prefix}pages/{quote(page.slug)}/index.html"


def home_href(prefix: str = "") -> str:
    return f"{prefix}index.html"


def unique_slug(base: str, used_slugs: dict[str, int]) -> str:
    count = used_slugs.get(base, 0)
    used_slugs[base] = count + 1
    return base if count == 0 else f"{base}-{count + 1}"


def load_pages() -> tuple[list[Page], dict[str, Page]]:
    excluded = {"index.md", "readme.md"}
    md_files = sorted(path for path in ROOT.glob("*.md") if path.name.lower() not in excluded)
    raw: list[tuple[Path, str, str, str | None, str]] = []
    used_slugs: dict[str, int] = {}

    for path in md_files:
        text = read_text(path)
        title = first_heading_or_stem(path, text)
        base_slug = slugify(path.stem)
        slug = unique_slug(base_slug, used_slugs)
        raw.append((path, title, slug, first_image(text), summarize(text)))

    pages = [
        Page(
            source=path,
            title=title,
            slug=slug,
            html="",
            summary=summary,
            image=image,
            updated=dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d"),
        )
        for path, title, slug, image, summary in raw
    ]

    lookup: dict[str, Page] = {}
    for page in pages:
        keys = {
            clean_title(page.source.stem),
            clean_title(page.title),
            clean_title(page.source.name.removesuffix(".md")),
        }
        for key in keys:
            lookup[key] = page
            display_key = display_text(key)
            if display_key:
                lookup[display_key] = page
            stripped_key = strip_markdown(key)
            if stripped_key:
                lookup[stripped_key] = page

    return pages, lookup


def parse_outline(index_text: str, page_lookup: dict[str, Page]) -> OutlineNode:
    root = OutlineNode("root", "root", 0)
    stack: list[OutlineNode] = [root]

    for raw_line in index_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            node = OutlineNode("section", display_text(heading.group(2)), level)
            while stack and stack[-1].level >= level:
                stack.pop()
            stack[-1].children.append(node)
            stack.append(node)
            continue
        wiki = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", stripped)
        if wiki:
            title = display_text(wiki.group(2) or wiki.group(1))
            target = clean_title(wiki.group(1))
            page = page_lookup.get(target) or page_lookup.get(display_text(target)) or page_lookup.get(strip_markdown(target))
            node = OutlineNode("link", title, stack[-1].level + 1, page)
            stack[-1].children.append(node)

    return root


def nav_sections(outline: OutlineNode) -> list[OutlineNode]:
    return [node for node in outline.children if node.type == "section"]


def section_markdown(node: OutlineNode) -> str:
    lines: list[str] = [f"# {node.title}", ""]

    def walk(item: OutlineNode) -> None:
        if item.type == "section":
            level = max(1, min(item.level - 1, 5))
            lines.append(f"{'#' * level} {item.title}")
            lines.append("")
            for child in item.children:
                walk(child)
        elif item.type == "link":
            lines.append(f"- [[{item.title}]]")

    for child in node.children:
        walk(child)
    return "\n".join(lines).strip() + "\n"


def attach_section_pages(outline: OutlineNode, pages: list[Page], lookup: dict[str, Page]) -> None:
    used_slugs: dict[str, int] = {}
    for page in pages:
        used_slugs[page.slug] = max(used_slugs.get(page.slug, 0), 1)

    today = dt.date.today().isoformat()
    for section in nav_sections(outline):
        page = lookup.get(section.title)
        if page:
            section.page = page
            continue

        slug = unique_slug(slugify(section.title), used_slugs)
        page = Page(
            source=None,
            title=section.title,
            slug=slug,
            html="",
            summary="",
            image=None,
            kind="Index",
            updated=today,
            raw=section_markdown(section),
        )
        section.page = page
        pages.append(page)
        lookup[section.title] = page


def render_menu(outline: OutlineNode, prefix: str = "") -> str:
    sections = nav_sections(outline)
    items = []
    for section in sections:
        href = page_href(section.page, prefix) if section.page else f"{prefix}#{slugify(section.title)}"
        items.append(f'<li><a href="{href}">{html.escape(section.title)}</a></li>')
    return "\n".join(items)


def iter_links(node: OutlineNode) -> Iterable[OutlineNode]:
    if node.type == "link":
        yield node
    for child in node.children:
        yield from iter_links(child)


def is_year_title(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", value.strip()))


def find_page_context(outline: OutlineNode, page: Page) -> tuple[str | None, str | None]:
    def walk(
        node: OutlineNode,
        current_section: str | None = None,
        current_year: str | None = None,
    ) -> tuple[str | None, str | None] | None:
        section = current_section
        year = current_year

        if node.type == "section":
            if node.level == 1:
                section = node.title
                year = None
            elif section == "Curation" and is_year_title(node.title):
                year = node.title

        if node.type == "link" and node.page is page:
            return section, year

        for child in node.children:
            found = walk(child, section, year)
            if found:
                return found
        return None

    return walk(outline) or (None, None)


def infer_page_year(page: Page | None) -> str | None:
    if not page:
        return None
    text = page.raw
    if page.source:
        text = read_text(page.source)
    match = re.search(r"\b(?:19|20)\d{2}\b", text)
    return match.group(0) if match else None


def render_outline_node(node: OutlineNode, depth: int = 0, prefix: str = "") -> str:
    if node.type == "link":
        label = html.escape(node.title)
        if node.page:
            return (
                f'<li class="archive-link depth-{depth}">'
                f'<a href="{page_href(node.page, prefix)}"><span>{label}</span>'
                f'<small>{html.escape(node.page.kind)}</small></a></li>'
            )
        return (
            f'<li class="archive-link archive-link--missing depth-{depth}">'
            f'<span>{label}</span><small>draft</small></li>'
        )

    child_html = "\n".join(render_outline_node(child, depth + 1, prefix) for child in node.children)
    if node.level <= 1:
        return (
            f'<section class="index-section" id="{slugify(node.title)}">'
            f'<div class="section-label">{html.escape(node.title)}</div>'
            f'<div class="section-body"><ul class="archive-list">{child_html}</ul></div>'
            "</section>"
        )
    return (
        f'<li class="archive-group depth-{depth}">'
        f'<p>{html.escape(node.title)}</p><ul>{child_html}</ul></li>'
    )


def find_section_for_page(outline: OutlineNode, page: Page) -> OutlineNode | None:
    for section in nav_sections(outline):
        if section.page is page or section.title == page.title:
            return section
    return None


def render_content_item(
    node: OutlineNode,
    prefix: str = "",
    show_summary: bool = False,
    show_meta: bool = False,
    meta_text: str | None = None,
) -> str:
    label = html.escape(node.title)
    if node.page:
        thumb = ""
        if node.page.image:
            thumb = (
                f'<span class="content-item__thumb" style="background-image:url('
                f'{html.escape(node.page.image, quote=True)});"></span>'
            )
        summary = (
            f'<span class="content-item__summary">{html.escape(node.page.summary or "Open entry")}</span>'
            if show_summary
            else ""
        )
        meta_value = meta_text or (node.page.updated if show_meta else "")
        meta = (
            f'<span class="content-item__meta">{html.escape(meta_value)}</span>'
            if meta_value
            else ""
        )
        return (
            f'<a class="content-item" href="{page_href(node.page, prefix)}">'
            f'{thumb}'
            f'<span class="content-item__main">'
            f'<span class="content-item__title">{label}</span>'
            f'{summary}'
            f'</span>'
            f'{meta}'
            f'</a>'
        )

    summary = (
        '<span class="content-item__summary">Markdown file not found yet.</span>'
        if show_summary
        else ""
    )
    meta = '<span class="content-item__meta">Draft</span>' if show_meta else ""
    return (
        f'<div class="content-item content-item--missing">'
        f'<span class="content-item__main">'
        f'<span class="content-item__title">{label}</span>'
        f'{summary}'
        f'</span>'
        f'{meta}'
        f'</div>'
    )


def render_section_branch(
    node: OutlineNode,
    prefix: str = "",
    depth: int = 0,
    section_title: str | None = None,
    current_year: str | None = None,
) -> str:
    if node.level == 1:
        section_title = node.title
        current_year = None
    elif section_title == "Curation" and is_year_title(node.title):
        current_year = node.title

    link_items = [child for child in node.children if child.type == "link"]
    section_items = [child for child in node.children if child.type == "section"]
    item_year = current_year if section_title == "Curation" else None

    if (
        node.level > 1
        and len(link_items) == 1
        and not section_items
        and slugify(link_items[0].title) == slugify(node.title)
    ):
        year = item_year or (infer_page_year(link_items[0].page) if section_title == "Curation" else None)
        return render_content_item(link_items[0], prefix, meta_text=year)

    links_html = "".join(
        render_content_item(
            child,
            prefix,
            meta_text=item_year or (infer_page_year(child.page) if section_title == "Curation" else None),
        )
        for child in link_items
    )
    nested_html = "".join(
        render_section_branch(child, prefix, depth + 1, section_title, current_year)
        for child in section_items
    )

    if node.level <= 1:
        return links_html + nested_html

    return (
        f'<section class="content-group content-group--depth-{depth}">'
        f'<header class="content-group__header">'
        f'<p>{html.escape(node.title)}</p>'
        f'</header>'
        f'<div class="content-group__body">{links_html}{nested_html}</div>'
        f'</section>'
    )


def render_section_index(section: OutlineNode, prefix: str = "") -> str:
    body = render_section_branch(section, prefix)
    return f'<div class="section-index">{body}</div>'


def remove_first_summary_line(text: str, summary: str) -> str:
    if not summary:
        return text
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped == "---" or stripped.startswith("#") or stripped.startswith("!"):
            continue
        if strip_markdown(stripped) == summary:
            return "\n".join(lines[:index] + lines[index + 1 :])
        break
    return text


def render_contact_qr_pairs(body_html: str) -> str:
    pattern = re.compile(
        r"<p>(WeChat|WhatsApp)</p>\s*"
        r'(<figure class="media"><img [^>]+></figure>)'
    )
    return pattern.sub(
        lambda m: (
            f'<div class="qr-row"><p>{m.group(1)}</p>{m.group(2)}</div>'
        ),
        body_html,
    )


def split_first_media(body_html: str) -> tuple[str, str]:
    pattern = re.compile(r'\s*(<figure class="media"><img [^>]+></figure>)', re.S)
    match = pattern.search(body_html)
    if not match:
        return "", body_html
    return match.group(1), pattern.sub("", body_html, count=1).strip()


def render_intro_name(value: str) -> str:
    spans: list[str] = []
    for index, character in enumerate(value):
        if character == " ":
            spans.append('<span class="title-gap" aria-hidden="true"> </span>')
            continue
        spans.append(
            f'<span class="title-char title-char--{index % 7}">{html.escape(character)}</span>'
        )
    return "".join(spans)


def render_home(outline: OutlineNode, pages: list[Page], page_lookup: dict[str, Page]) -> str:
    intro_name = render_intro_name(SITE["name"])
    content = f"""
<main class="top-page">
  <div class="top-loading-dot" aria-hidden="true"></div>
  <section class="top-header" aria-label="Home">
    <h1 class="top-header__title" aria-label="{html.escape(SITE["name"], quote=True)}">{intro_name}</h1>
  </section>
  <div class="top-background-blank" aria-hidden="true"></div>
</main>
"""
    return layout("Home", content, outline, body_class="home")


def asset_version(filename: str) -> str:
    path = ASSETS / filename
    if not path.exists():
        return "missing"
    return hashlib.sha1(path.read_bytes()).hexdigest()[:10]


def render_page(page: Page, outline: OutlineNode, page_lookup: dict[str, Page]) -> str:
    prefix = "../../"
    section = find_section_for_page(outline, page)
    is_top_level_page = section is not None
    page_section, page_year = find_page_context(outline, page)
    if page_section == "Curation" and not page_year:
        page_year = infer_page_year(page)
    page_kicker = (
        f'<p class="article-kicker">{html.escape(page_year)}</p>'
        if page_section == "Curation" and page_year
        else ""
    )
    body_class = "detail section-detail" if page.kind == "Index" else "detail top-level-detail" if is_top_level_page else "detail"
    body_class = f"{body_class} page-{page.slug}"
    if page.kind == "Index":
        body_html = render_section_index(section, prefix) if section else markdown_to_html(page.raw, page_lookup, page.title, prefix)
        content = f"""
<main class="article-shell section-shell">
  <article class="article">
    <header class="article-header">
      <h1>{html.escape(page.title)}</h1>
    </header>
    <div class="prose">
      {body_html}
    </div>
  </article>
</main>
"""
    else:
        body_text = read_text(page.source) if page.source else page.raw
        if is_top_level_page:
            body_html = markdown_to_html(
                remove_first_summary_line(body_text, page.summary),
                page_lookup,
                page.title,
                prefix,
            )
            if page.slug == "contact":
                body_html = render_contact_qr_pairs(body_html)
            if page.slug == "about":
                portrait_html, body_html = split_first_media(body_html)
                content = f"""
<main class="article-shell top-level-shell about-shell">
  <article class="article about-article">
    <div class="about-copy">
      <header class="article-header">
        {page_kicker}
        <h1>{html.escape(page.title)}</h1>
        {f'<p class="article-summary">{html.escape(page.summary)}</p>' if page.summary else ''}
      </header>
      <div class="prose">
        {body_html}
      </div>
    </div>
    {f'<aside class="about-portrait" aria-label="Portrait">{portrait_html}</aside>' if portrait_html else ''}
  </article>
</main>
"""
            else:
                content = f"""
<main class="article-shell top-level-shell">
  <article class="article">
    <header class="article-header">
      <h1>{html.escape(page.title)}</h1>
      {f'<p class="article-summary">{html.escape(page.summary)}</p>' if page.summary else ''}
    </header>
    <div class="prose">
      {body_html}
    </div>
  </article>
</main>
"""
        else:
            body_html = markdown_to_html(body_text, page_lookup, page.title, prefix)
            content = f"""
<main class="article-shell page-shell">
  <article class="article">
      <header class="article-header">
        {page_kicker}
        <h1>{html.escape(page.title)}</h1>
      </header>
    <div class="prose">
      {body_html}
    </div>
  </article>
</main>
"""
    return layout(page.title, content, outline, body_class=body_class, prefix=prefix)


def layout(title: str, content: str, outline: OutlineNode, body_class: str = "", prefix: str = "") -> str:
    page_title = SITE["name"] if title == "Home" else f"{title} | {SITE['name']}"
    menu = render_menu(outline, prefix)
    year = dt.date.today().year
    css_version = asset_version("styles.css")
    js_version = asset_version("site.js")
    header_title = "" if body_class == "home" else f'<a class="site-title" href="{home_href(prefix)}">{html.escape(SITE["name"])}</a>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(SITE["description"], quote=True)}">
  <link rel="stylesheet" href="{prefix}assets/styles.css?v={css_version}">
  <script src="{prefix}assets/site.js?v={js_version}" defer></script>
</head>
<body class="{html.escape(body_class)}">
  <header class="site-header">
    <button class="menu-button" type="button" data-menu-open>Menu</button>
    {header_title}
  </header>
  <div class="site-menu" data-menu hidden>
    <div class="menu-panel">
      <div class="menu-top">
        <button class="menu-button" type="button" data-menu-close>Close</button>
      </div>
      <nav aria-label="Menu"><ul>{menu}</ul></nav>
    </div>
  </div>
  {content}
  <footer class="site-footer">
    <p>© {year} {html.escape(SITE["name"])}</p>
    <p>Built from Markdown. Daily GitHub Pages rebuild enabled.</p>
  </footer>
</body>
</html>
"""


def copy_assets() -> None:
    target = OUT / "assets"
    target.mkdir(parents=True, exist_ok=True)
    for asset in ASSETS.glob("*"):
        if asset.is_file():
            shutil.copy2(asset, target / asset.name)


def write_sitemap(pages: list[Page]) -> None:
    today = dt.date.today().isoformat()
    urls = ["  <url><loc>/</loc><lastmod>{}</lastmod></url>".format(today)]
    for page in pages:
        urls.append(
            f"  <url><loc>/{page_href(page)}</loc><lastmod>{html.escape(page.updated)}</lastmod></url>"
        )
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n",
        encoding="utf-8",
    )
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n", encoding="utf-8")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    pages, lookup = load_pages()
    index_path = ROOT / "index.md"
    if not index_path.exists():
        raise SystemExit("index.md is required")
    outline = parse_outline(read_text(index_path), lookup)
    attach_section_pages(outline, pages, lookup)

    copy_assets()
    (OUT / "index.html").write_text(render_home(outline, pages, lookup), encoding="utf-8")

    for page in pages:
        page_dir = OUT / "pages" / page.slug
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(render_page(page, outline, lookup), encoding="utf-8")

    write_sitemap(pages)
    print(f"Built {len(pages)} pages into {OUT}")


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
