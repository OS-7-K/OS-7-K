import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USERNAME = os.environ.get("GITHUB_USERNAME", "Osama7amed04")
README_PATH = os.environ.get("README_PATH", "README.md")
MAX_REPOS = int(os.environ.get("MAX_REPOS", "6"))

START_MARKER = "<!-- REPOS:START -->"
END_MARKER = "<!-- REPOS:END -->"

LANGUAGES_START_MARKER = "<!-- LANGUAGES:START -->"
LANGUAGES_END_MARKER = "<!-- LANGUAGES:END -->"

ALLOWED_LANGUAGES = {
    "Dart": {"color": "00B4D8", "logo": "dart", "logo_color": "white"},
    "Python": {"color": "1E3A8A", "logo": "python", "logo_color": "white"},
}


# ---------------- FETCH ----------------

def fetch_repositories():
    url = f"https://api.github.com/users/{USERNAME}/repos?sort=pushed&direction=desc&per_page=100"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-readme-updater",
    }

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"GitHub API error: {e}", file=sys.stderr)
        raise


def fetch_json(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-readme-updater",
    }

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)

    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


# ---------------- HELPERS ----------------

def sanitize_text(value):
    if not value:
        return "No description yet."

    return re.sub(r"\s+", " ", value).strip()


def format_date(value):
    if not value:
        return "recent"

    date = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return date.strftime("%b %Y")


def get_languages(repo, cache):
    name = repo["name"]

    if name in cache:
        return cache[name]

    url = repo.get("languages_url")
    if not url:
        cache[name] = {}
        return {}

    cache[name] = fetch_json(url)
    return cache[name]


def detect_language(languages):
    if languages.get("Dart", 0) > 0:
        return "Flutter"
    if languages.get("Python", 0) > 0:
        return "Python"
    return "Code"


# ---------------- REPOS SECTION ----------------

def build_repos(repos, cache):
    repos = [
        r for r in repos
        if not r.get("fork") and not r.get("archived")
    ][:MAX_REPOS]

    if not repos:
        return "No repositories found."

    out = []

    for r in repos:
        langs = get_languages(r, cache)

        out += [
            f"### [{r['name']}]({r['html_url']})",
            "",
            sanitize_text(r.get("description")),
            "",
            f"`{detect_language(langs)}` | ⭐ {r.get('stargazers_count',0)} | 🍴 {r.get('forks_count',0)} | 📅 {format_date(r.get('pushed_at'))}",
            "",
        ]

    return "\n".join(out)


# ---------------- LANGUAGE SECTION ----------------

def build_languages(repos, cache):
    totals = {k: 0 for k in ALLOWED_LANGUAGES}

    for r in repos:
        if r.get("fork") or r.get("archived"):
            continue

        langs = get_languages(r, cache)

        for lang, val in langs.items():
            if lang in totals:
                totals[lang] += val

    total = sum(totals.values())

    if total == 0:
        return "No language data available."

    labels, data, colors, badges = [], [], [], []

    for lang, val in sorted(totals.items(), key=lambda x: x[1], reverse=True):
        if val == 0:
            continue

        percent = round((val / total) * 100, 1)
        meta = ALLOWED_LANGUAGES[lang]

        labels.append(lang)
        data.append(percent)
        colors.append(f"#{meta['color']}")

        badges.append(
            f'<img src="https://img.shields.io/badge/{lang}-{percent}%25-{meta["color"]}?style=for-the-badge&logo={meta["logo"]}&logoColor={meta["logo_color"]}" />'
        )

    chart = {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": data,
                "backgroundColor": colors
            }]
        }
    }

    url = f"https://quickchart.io/chart?c={quote(json.dumps(chart))}"

    return f"""
<p align="center">
  <img src="{url}" />
</p>

<p align="center">
  {' '.join(badges)}
</p>
"""


# ---------------- MARKER HANDLING ----------------

def replace(readme, start, end, content):
    if start not in readme or end not in readme:
        return readme

    before, rest = readme.split(start, 1)
    _, after = rest.split(end, 1)

    return before + start + "\n" + content + "\n" + end + after


def ensure(readme, start, end, content):
    if start in readme and end in readme:
        return readme
    return readme.strip() + f"\n\n{start}\n{content}\n{end}\n"


def update_readme(repo_section, lang_section):
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    readme = ensure(readme, START_MARKER, END_MARKER, repo_section)
    readme = ensure(readme, LANGUAGES_START_MARKER, LANGUAGES_END_MARKER, lang_section)

    readme = replace(readme, START_MARKER, END_MARKER, repo_section)
    readme = replace(readme, LANGUAGES_START_MARKER, LANGUAGES_END_MARKER, lang_section)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)


# ---------------- MAIN ----------------

def main():
    repos = fetch_repositories()
    cache = {}

    repo_section = build_repos(repos, cache)
    lang_section = build_languages(repos, cache)

    update_readme(repo_section, lang_section)


if __name__ == "__main__":
    main()