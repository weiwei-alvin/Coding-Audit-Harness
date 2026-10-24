"""Browser evidence collector: screenshots, aria snapshot, keyboard walkthrough, console.

Tier-2 capture with Tier-1 deterministic assertions. Playwright is imported lazily
so the rest of the CLI keeps working without a browser toolchain; the collector
never claims UI acceptance.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from .contract import ROOT, engine_hash, sha

VIEWPORTS = (("desktop", 1440, 900), ("tablet", 768, 1024), ("narrow", 390, 844))
DEFAULT_TABS = 12
DEFAULT_WAIT_MS = 50
LIMITATIONS = [
    "Screenshots are captured, not judged; visual quality, contrast and layout verdicts belong to T-004 review.",
    "Accessible names follow a fixed precedence (aria-label, aria-labelledby, label, text, title, alt); this is a heuristic, not the full AccName specification.",
    "Forced-colors and reduced-motion are browser emulations, not real user settings or assistive technology.",
    "The keyboard walkthrough presses Tab a fixed number of times; it does not script flows, arrow-key widget behaviour or pointer input.",
    "This collection is not UI acceptance; ui_acceptance stays UNVERIFIED until T-004/T-005 gates have three-tier evidence.",
]

ACTIVE_ELEMENT_JS = """() => {
  const el = document.activeElement;
  if (!el || el === document.body) {
    return { tag: 'body', operable: false, accessible_name: '', id: '' };
  }
  const tag = el.tagName.toLowerCase();
  const operable = ['a', 'button', 'input', 'select', 'textarea', 'summary'].includes(tag)
    || (typeof el.tabIndex === 'number' && el.tabIndex >= 0);
  const name = (() => {
    const aria = el.getAttribute('aria-label');
    if (aria && aria.trim()) { return aria.trim(); }
    const by = el.getAttribute('aria-labelledby');
    if (by) {
      const text = by.split(/\\s+/)
        .map((id) => (document.getElementById(id) || {}).textContent || '')
        .join(' ').trim();
      if (text) { return text; }
    }
    if (el.labels && el.labels.length) {
      return Array.from(el.labels).map((l) => l.textContent.trim()).join(' ').trim();
    }
    const text = el.textContent;
    if (text && text.trim()) { return text.trim().replace(/\\s+/g, ' ').slice(0, 80); }
    const title = el.getAttribute('title');
    if (title && title.trim()) { return title.trim(); }
    const alt = el.getAttribute('alt');
    if (alt) { return alt.trim(); }
    return '';
  })();
  return { tag: tag, operable: operable, accessible_name: name, id: el.id || '' };
}"""


def _artifact_entry(path, base):
    raw = path.read_bytes()
    return dict(path=path.relative_to(base).as_posix(), sha256=sha(raw), bytes=len(raw))


def collect_evidence(page_input, output, tabs=DEFAULT_TABS, wait_ms=DEFAULT_WAIT_MS):
    """Drive a real browser over one page and write a create-only evidence directory."""
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError as exc:
        raise ValueError(
            "playwright is not installed; run: python -m venv .venv && "
            ".venv\\Scripts\\pip install -r requirements.txt && "
            ".venv\\Scripts\\python -m playwright install chromium") from exc

    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Evidence directory already exists: {output}")
    page_input = Path(page_input)
    if page_input.is_file():
        url = page_input.resolve().as_uri()
        page_sha = sha(page_input.read_bytes())
    else:
        url = str(page_input)
        page_sha = None

    started = datetime.now(timezone.utc).isoformat()
    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch()
            try:
                page = browser.new_page()
                messages = []
                page.on("console", lambda m: messages.append(dict(type=m.type, text=m.text)))
                page.on("pageerror", lambda e: messages.append(dict(type="pageerror", text=str(e))))
                page.goto(url, wait_until="load")
                if wait_ms > 0:
                    page.wait_for_timeout(wait_ms)
                title = page.title()

                (output / "screenshots").mkdir(parents=True)
                for name, width, height in VIEWPORTS:
                    page.set_viewport_size(dict(width=width, height=height))
                    page.screenshot(path=str(output / "screenshots" / f"{name}.png"))
                page.set_viewport_size(dict(width=1440, height=900))
                page.emulate_media(reduced_motion="reduce")
                page.screenshot(path=str(output / "screenshots" / "reduced-motion.png"))
                page.emulate_media(reduced_motion="no-preference")
                page.emulate_media(forced_colors="active")
                page.screenshot(path=str(output / "screenshots" / "forced-colors.png"))
                page.emulate_media(forced_colors="none")

                aria = page.locator("body").aria_snapshot()
                (output / "aria-snapshot.yaml").write_text(aria + "\n", encoding="utf-8")

                sequence = []
                for step in range(1, tabs + 1):
                    page.keyboard.press("Tab")
                    info = page.evaluate(ACTIVE_ELEMENT_JS)
                    sequence.append(dict(step=step, **info))
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise ValueError(f"Browser run failed for {url}: {exc}") from exc

    errors = [m for m in messages if m["type"] in ("error", "pageerror")]
    console_payload = dict(errors=errors, messages=messages)
    (output / "console.json").write_text(
        _json_text(console_payload), encoding="utf-8")

    keyboard_payload = dict(tabs_requested=tabs, sequence=sequence,
        operable_reached=sum(1 for s in sequence if s["operable"]))
    (output / "keyboard.json").write_text(
        _json_text(keyboard_payload), encoding="utf-8")

    findings = []
    for message in errors:
        findings.append(dict(code="CONSOLE_ERROR", severity="blocking",
            message="Console reported an error while the page was open.",
            evidence=message["text"][:300]))
    for step in sequence:
        if step["operable"] and not step["accessible_name"].strip():
            findings.append(dict(code="UNNAMED_OPERABLE", severity="major",
                message="An operable element reachable by keyboard has no accessible name.",
                evidence=f"step {step['step']}: <{step['tag']}> id={step['id'] or '-'}"))
    if not keyboard_payload["operable_reached"]:
        findings.append(dict(code="NO_OPERABLE_REACHED", severity="major",
            message="The Tab walkthrough reached no operable element; the page may not be keyboard operable.",
            evidence=f"tabs pressed: {tabs}"))

    status = "FAIL" if findings else "PASS"
    finished = datetime.now(timezone.utc).isoformat()
    report = dict(schema_version="0.1", kind="browser_evidence", status=status,
        collected_at=finished, started_at=started, ui_acceptance="UNVERIFIED",
        page=dict(url=url, title=title, sha256=page_sha),
        engine_hash=engine_hash(),
        viewports=[dict(label=name, width=width, height=height) for name, width, height in VIEWPORTS],
        console=dict(errors=len(errors), messages=len(messages)),
        keyboard=dict(tabs_requested=tabs, operable_reached=keyboard_payload["operable_reached"]),
        findings=findings,
        verification=dict(reproduce=[
            "python -m ui_design_harness collect --input <page.html> --output <new-evidence-directory>",
        ]),
        limitations=list(LIMITATIONS))
    (output / "report.json").write_text(_json_text(report), encoding="utf-8")

    artifacts = [_artifact_entry(output / "report.json", output)]
    for name in ("aria-snapshot.yaml", "keyboard.json", "console.json"):
        artifacts.append(_artifact_entry(output / name, output))
    for path in sorted((output / "screenshots").glob("*.png")):
        artifacts.append(_artifact_entry(path, output))
    manifest = dict(schema_version="0.1", kind="browser_evidence_manifest",
        command=[sys.executable] + sys.argv[1:],
        started_at=started, finished_at=finished,
        exit_code=0 if status == "PASS" else 1,
        page=dict(url=url, title=title, sha256=page_sha), artifacts=artifacts,
        ui_acceptance="UNVERIFIED")
    (output / "manifest.json").write_text(_json_text(manifest), encoding="utf-8")
    return report


def _json_text(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
