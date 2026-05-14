from dataclasses import dataclass
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.mianshiya.com"


@dataclass(frozen=True)
class InterviewQuestion:
    title: str
    url: str


def search_interview_questions(keyword: str, limit: int = 10) -> list[InterviewQuestion]:
    search_text = keyword.strip()
    if not search_text:
        return []

    url = f"{BASE_URL}/search/all?searchText={quote(search_text)}"
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=5,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    questions: list[InterviewQuestion] = []
    seen_urls: set[str] = set()

    for element in soup.select(".ant-table-cell > a"):
        title = element.get_text(strip=True)
        href = element.get("href", "").strip()
        if not title or not href:
            continue

        absolute_url = urljoin(BASE_URL, href)
        if absolute_url in seen_urls:
            continue

        questions.append(InterviewQuestion(title=title, url=absolute_url))
        seen_urls.add(absolute_url)

        if len(questions) >= limit:
            break

    return questions


def format_interview_questions(questions: list[InterviewQuestion]) -> str:
    if not questions:
        return ""

    return "\n".join(
        f"[{index}] {question.title} - {question.url}"
        for index, question in enumerate(questions, start=1)
    )
