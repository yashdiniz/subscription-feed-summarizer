import instructor
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List
import os

load_dotenv()


# Ponytail: Pydantic models map directly to JSON schema. Clean, simple.
class Article(BaseModel):
    link: str = Field(..., description="URL to article")
    author: str = Field(..., description="Author/Creator/Publisher of content")
    title: str = Field(
        ...,
        description="One phrase title",
    )
    summary: str = Field(
        ...,
        description="Summary of the article content, at least 20 words",
        min_length=20,
    )
    opinionated: bool = Field(
        ...,
        description="True if from curated/editorial sources (blogs, newsletters); False if from organic/social sources (Reddit, Hacker News, GitHub, LinkedIn).",
    )


class ArticleList(BaseModel):
    articles: List[Article] = Field(
        ...,
        description="List of articles. No extra prose or filler, no HTML/XML. \
                Summarize all data shared, do not add or remove from what user provides.",
    )


def generate_structured_articles(content: str) -> ArticleList:
    # Handles prompting for JSON, validation, and retries. Lazy and robust.
    # Make sure to set your GEMINI_API_KEY environment variable.
    client = instructor.from_provider("google/gemini-flash-lite-latest")

    return client.create(
        response_model=ArticleList,
        messages=[{"role": "user", "content": content}],
    )


if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        raise ValueError(
            "GEMINI_API_KEY environment variable not set. Please set it to run the test."
        )
