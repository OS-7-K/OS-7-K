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
    "Python": {"color": "F2C94C", "logo": "python", "logo_color": "111111"},
}


def fetch_repositories():
    url = f"https://api.github.com/users/{USERNAME}/repos?sort=pushed&direction=desc&per_page=100"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme-updater",
    }

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as error:
        print(f"Failed to fetch repositories: {error}", file=sys.stderr)
        raise


def fetch_json(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme-updater",
    }

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def format_date(value):
    if not value:
        return "recently"

    date = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return date.strftime("%b %Y")


def sanitize_text(value):
    replacements = {
        "\u2013": " - ",
        "\u2014": " - ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
    }

    text = value or "No description yet."
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip()

    return text or "No description yet."


def get_repository_languages(repo, language_cache):
    name = repo.get("name", "")
    if name in language_cache:
        return language_cache[name]

    languages_url = repo.get("languages_url")
    if not languages_url:
        language_cache[name] = {}
        return {}

    language_cache[name] = fetch_json(languages_url)
    return language_cache[name]


def display_repository_language(repo, languages):
    if languages.get("Dart", 0) > 0:
        return "Flutter"

    if languages.get("Python", 0) > 0:
        return "Python"

    return repo.get("language") or "Code"


def build_repository_section(repositories, language_cache):
    filtered = [
        repo
        for repo in repositories
        if not repo.get("fork")
        and not repo.get("archived")
        and repo.get("name", "").lower() != USERNAME.lower()
    ][:MAX_REPOS]

    if not filtered:
        return "No public repositories found yet."

    lines = []
    for repo in filtered:
        name = repo["name"]
        url = repo["html_url"]
        description = sanitize_text(repo.get("description"))
        languages = get_repository_languages(repo, language_cache)
        language = display_repository_language(repo, languages)
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        updated = format_date(repo.get("pushed_at"))

        lines.extend(
            [
                f"### [{name}]({url})",
                "",
                description,
                "",
                f"`{language}`  |  Stars: `{stars}`  |  Forks: `{forks}`  |  Updated: `{updated}`",
                "",
            ]
        )

    return "\n".join(lines).rstrip()


def build_language_section(repositories, language_cache):
    totals = {language: 0 for language in ALLOWED_LANGUAGES}

    for repo in repositories:
        if repo.get("fork") or repo.get("archived") or repo.get("name", "").lower() == USERNAME.lower():
            continue

        languages = get_repository_languages(repo, language_cache)
        for language, bytes_count in languages.items():
            if language in totals:
                totals[language] += bytes_count

    total_bytes = sum(totals.values())
    if total_bytes == 0:
        return "No Dart or Python code detected in public repositories yet."

    labels = []
    data = []
    colors = []
    badges = []

    for language, bytes_count in sorted(totals.items(), key=lambda item: item[1], reverse=True):
        if bytes_count == 0:
            continue

        percent = round((bytes_count / total_bytes) * 100, 1)
        meta = ALLOWED_LANGUAGES[language]
        labels.append(language)
        data.append(percent)
        colors.append(f"#{meta['color']}")
        badges.append(
            f'<img src="https://img.shields.io/badge/{language}-{percent}%25-{meta["color"]}'
            f'?style=for-the-badge&logo={meta["logo"]}&logoColor={meta["logo_color"]}" alt="{language} {percent}%" />'
        )

    chart_config = {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "data": data,
                    "backgroundColor": colors,
                    "borderColor": "#0d1117",
                    "borderWidth": 2,
                }
            ],
        },
        "options": {
            "plugins": {
                "legend": {
                    "position": "bottom",
                    "labels": {"color": "#c9d1d9", "font": {"size": 14}},
                }
            }
        },
    }
    chart_url = f"https://quickchart.io/chart?width=420&height=260&c={quote(json.dumps(chart_config, separators=(',', ':')))}"

    return "\n".join(
        [
            '<p align="center">',
            f'  <img src="{chart_url}" alt="Dart and Python language usage chart" />',
            "</p>",
            "",
            '<p align="center">',
            f"  {' '.join(badges)}",
            "</p>",
        ]
    )


def replace_between_markers(readme, start_marker, end_marker, section):
    if start_marker not in readme or end_marker not in readme:
        return readme

    before, rest = readme.split(start_marker, 1)
    _, after = rest.split(end_marker, 1)
    return f"{before}{start_marker}\n{section}\n{end_marker}{after}"


def update_readme(repository_section, language_section):
    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if START_MARKER not in readme or END_MARKER not in readme:
        raise RuntimeError("Repository markers were not found in README.md")

    updated = replace_between_markers(readme, START_MARKER, END_MARKER, repository_section)
    updated = replace_between_markers(updated, LANGUAGES_START_MARKER, LANGUAGES_END_MARKER, language_section)

    with open(README_PATH, "w", encoding="utf-8", newline="\n") as file:
        file.write(updated)


def main():
    repositories = fetch_repositories()
    language_cache = {}
    repository_section = build_repository_section(repositories, language_cache)
    language_section = build_language_section(repositories, language_cache)
    update_readme(repository_section, language_section)


if __name__ == "__main__":
    main()
