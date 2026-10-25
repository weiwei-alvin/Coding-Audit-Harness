"""Fail CI on broken repository-relative Markdown links in README files."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\((<?[^\s)]+>?)(?:\s+[^)]*)?\)")
SKIP = ("http:", "https:", "mailto:", "data:", "tel:", "#", "//")


def broken_links(root=ROOT):
    errors = []
    for readme in sorted(root.rglob("README*.md")):
        if any(part.startswith(".") and part != "." for part in readme.relative_to(root).parts):
            continue
        text = readme.read_text(encoding="utf-8")
        text = re.sub(r"^`{3}.*?^`{3}", "", text, flags=re.M | re.S)
        for match in MARKDOWN_LINK.finditer(text):
            url = match.group(1).strip("<>")
            if url.startswith(SKIP) or url.startswith("{{"):
                continue
            location = unquote(url.split("#")[0].split("?")[0])
            if not location:
                continue
            target = readme.parent / location
            if not target.exists():
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{readme.relative_to(root)}:{line} broken relative link {url}")
    return errors


if __name__ == "__main__":
    errors = broken_links()
    for error in errors:
        print(error, file=sys.stderr)
    print(f"README relative links: {'FAIL' if errors else 'PASS'} ({len(errors)} missing)")
    sys.exit(1 if errors else 0)
