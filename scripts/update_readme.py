import json
import os
import re
import sys
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USERNAME = os.environ.get("GITHUB_USERNAME", "Osama7amed04")
README_PATH = os.environ.get("README_PATH", "README.md")
MAX_REPOS = int(os.environ.get("MAX_REPOS", "6"))
START_MARKER = "<!-- REPOS:START -->"
END_MARKER = "<!-- REPOS:END -->"


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


def build_repository_section(repositories):
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
        language = repo.get("language") or "Code"
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


def update_readme(section):
    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if START_MARKER not in readme or END_MARKER not in readme:
        raise RuntimeError("Repository markers were not found in README.md")

    before, rest = readme.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    updated = f"{before}{START_MARKER}\n{section}\n{END_MARKER}{after}"

    with open(README_PATH, "w", encoding="utf-8", newline="\n") as file:
        file.write(updated)


def main():
    repositories = fetch_repositories()
    section = build_repository_section(repositories)
    update_readme(section)


if __name__ == "__main__":
    main()
