"""Crawls every class -> lesson plan -> materials and validates that every PDF,
every video, and every hyperlink embedded inside the PDFs actually loads.

This is the reliable way to answer "are all the PDFs and videos playing?" for
the whole catalogue — the media are plain URLs, so reachability + content-type
(and, for PDFs, the %PDF magic and the in-document links) is the real signal.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from utils.eg_api import EgApi, best_video_urls
from utils import link_check


@dataclass
class Item:
    cls: str
    topic: str
    label: str
    url: str
    kind: str          # "pdf" | "video" | "pdf-link"
    ok: bool = False
    status: int = 0
    note: str = ""


@dataclass
class Report:
    items: list = field(default_factory=list)
    classes: int = 0
    plans: int = 0

    def of_kind(self, kind: str):
        return [i for i in self.items if i.kind == kind]

    def broken(self, kind: str = None):
        pool = self.items if kind is None else self.of_kind(kind)
        return [i for i in pool if not i.ok]


def run_audit(
    mobile: str,
    base_url: str = None,
    class_limit: int = None,
    plan_limit: int = None,
) -> Report:
    api = EgApi(base_url=base_url) if base_url else EgApi()
    api.login(mobile)
    sid = api.school_id()
    classes = api.classes(sid)
    if class_limit:
        classes = classes[:class_limit]

    report = Report(classes=len(classes))
    url_cache = {}  # url -> link_check.UrlResult (dedupe network work)
    pdf_link_urls = []  # (cls, topic, link_url) to check after crawl

    def check(url, kind):
        if url in url_cache:
            return url_cache[url]
        res = link_check.check_url(url, kind=kind)
        url_cache[url] = res
        return res

    for c in classes:
        cname = c.get("class_name") or c.get("name") or c.get("id")
        plans = api.plans(c.get("id"))
        if plan_limit:
            plans = plans[:plan_limit]
        report.plans += len(plans)

        for p in plans:
            topic = p.get("display_name") or p.get("name") or p.get("id")
            detail = api.plan_detail(p.get("id"))

            for pdf in detail.get("pdfs", []) or []:
                url = pdf.get("pdf_url", "")
                label = pdf.get("title", "") or "(untitled pdf)"
                if not url:
                    report.items.append(Item(cname, topic, label, url, "pdf",
                                              False, 0, "no pdf_url"))
                    continue
                # Download the PDF (verifies %PDF) and pull its embedded links.
                if url in url_cache:
                    res = url_cache[url]
                    links = []
                else:
                    res, links = link_check.fetch_pdf_and_links(url)
                    url_cache[url] = res
                    for lk in links:
                        pdf_link_urls.append((cname, f"{topic} / {label}", lk))
                report.items.append(Item(cname, topic, label, url, "pdf",
                                          res.ok, res.status, res.note))

            for v in detail.get("videos", []) or []:
                label = v.get("display_name", "") or "(untitled video)"
                urls = best_video_urls(v)
                if not urls:
                    report.items.append(Item(cname, topic, label, "", "video",
                                              False, 0, "no playable url"))
                    continue
                for lang, url in urls:
                    res = check(url, "video")
                    report.items.append(Item(cname, topic, f"{label} [{lang}]",
                                              url, "video", res.ok, res.status, res.note))

    # In-PDF embedded links (videos / web pages the teacher can tap inside a PDF).
    for cname, topic, url in pdf_link_urls:
        res = check(url, "any")
        report.items.append(Item(cname, topic, "in-PDF link", url, "pdf-link",
                                  res.ok, res.status, res.note))

    return report


def write_markdown(report: Report, path):
    lines = ["# Lesson Plan link audit", ""]
    lines.append(f"- Classes crawled: **{report.classes}**")
    lines.append(f"- Lesson plans crawled: **{report.plans}**")
    for kind, label in [("pdf", "PDFs"), ("video", "Videos"), ("pdf-link", "In-PDF links")]:
        pool = report.of_kind(kind)
        bad = [i for i in pool if not i.ok]
        lines.append(f"- {label}: **{len(pool)}** checked, **{len(bad)}** broken")
    lines.append("")

    broken = report.broken()
    if not broken:
        lines.append("✅ All PDFs, videos, and in-PDF links loaded.")
    else:
        lines.append("## ❌ Broken items")
        lines.append("")
        lines.append("| Class | Topic | Kind | Item | Status | Note | URL |")
        lines.append("|---|---|---|---|---|---|---|")
        for i in broken:
            note = (i.note or "").replace("|", "/")
            lines.append(
                f"| {i.cls} | {i.topic} | {i.kind} | {i.label} | {i.status} | {note} | {i.url[:80]} |"
            )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
