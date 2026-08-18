"""Lightweight lexicon-based sentiment analysis for comments and transcripts.

This module provides a simple, dependency-free sentiment scorer inspired by
VADER (Valence Aware Dictionary and sEntiment Reasoner). It uses a built-in
lexicon of positive and negative words and produces a compound score from
-1.0 (very negative) to +1.0 (very positive).

No external dependencies (NLTK, transformers, etc.) are required. This makes
the package easy to install while still providing useful sentiment signals
for research workflows.

For production-grade sentiment analysis, researchers can feed the exported
CSV/JSONL data into NLTK VADER, HuggingFace transformers, or other NLP tools.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import Comment, VideoResult


# ---------------------------------------------------------------------------
# Lexicon (curated subset of VADER-style valence scores)
# ---------------------------------------------------------------------------

_POSITIVE_WORDS: dict[str, float] = {
    "good": 0.9, "great": 1.8, "excellent": 2.5, "amazing": 2.6,
    "awesome": 2.5, "fantastic": 2.5, "wonderful": 2.5, "best": 2.5,
    "love": 2.5, "loved": 2.5, "loving": 2.2, "like": 1.0, "liked": 1.0,
    "happy": 2.0, "glad": 1.8, "beautiful": 1.8, "perfect": 2.5,
    "brilliant": 2.2, "superb": 2.5, "outstanding": 2.5, "incredible": 2.5,
    "remarkable": 2.0, "fabulous": 2.5, "enjoy": 1.8, "enjoyed": 1.8,
    "enjoying": 1.8, "nice": 1.2, "cool": 1.0, "fun": 1.2, "funny": 1.5,
    "helpful": 1.8, "useful": 1.5, "informative": 1.5, "clear": 0.8,
    "easy": 0.8, "recommend": 1.8, "recommended": 1.8, "thanks": 1.5,
    "thank": 1.5, "appreciate": 1.8, "appreciated": 1.8, "well": 1.0,
    "better": 1.2, "super": 1.8, "positive": 1.2, "win": 1.5,
    "winning": 1.5, "won": 1.5, "success": 1.8, "successful": 1.8,
    "inspiring": 2.0, "inspired": 1.8, "motivating": 1.8, "motivated": 1.5,
    "impressive": 1.8, "stunning": 2.0, "gorgeous": 2.0, "lovely": 2.0,
    "favorite": 2.0, "favourite": 2.0, "masterpiece": 2.5, "legend": 2.0,
    "legendary": 2.5, "genius": 2.2, "talented": 1.8, "skillful": 1.5,
}

_NEGATIVE_WORDS: dict[str, float] = {
    "bad": -0.9, "terrible": -2.5, "horrible": -2.5, "awful": -2.0,
    "worst": -2.5, "hate": -2.5, "hated": -2.5, "hating": -2.2,
    "dislike": -1.5, "disliked": -1.5, "disgusting": -2.5, "stupid": -1.8,
    "dumb": -1.5, "idiot": -1.8, "idiotic": -2.0, "pathetic": -2.0,
    "useless": -1.8, "boring": -1.5, "bored": -1.2, "waste": -1.8,
    "wasted": -1.8, "wasting": -1.5, "poor": -1.2, "poorly": -1.2,
    "disappointing": -1.8, "disappointed": -1.8, "disappointment": -1.8,
    "frustrating": -1.5, "frustrated": -1.5, "annoying": -1.5,
    "annoyed": -1.2, "confusing": -1.0, "confused": -1.0,
    "broken": -1.2, "fail": -1.5, "failed": -1.5, "failure": -1.8,
    "cringe": -1.5, "cringey": -1.8, "trash": -2.0, "garbage": -2.0,
    "scam": -2.5, "fake": -1.5, "lies": -1.5, "lying": -1.5,
    "wrong": -1.0, "sad": -1.0, "sadly": -1.0, "unfortunately": -1.0,
    "negative": -1.2, "lost": -1.0, "lose": -1.2, "losing": -1.2,
    "loser": -1.8, "painful": -1.5, "painfully": -1.5, "hurt": -1.2,
    "hurts": -1.2, "hated": -2.5, "rubbish": -2.0, "nonsense": -1.2,
}

# Boosters that intensify the following word
_BOOSTERS: dict[str, float] = {
    "very": 1.3, "really": 1.2, "so": 1.2, "extremely": 1.5,
    "absolutely": 1.4, "totally": 1.3, "completely": 1.3,
    "incredibly": 1.4, "highly": 1.3, "utterly": 1.4,
}

# Negators that flip the sentiment of the following word
_NEGATORS: frozenset[str] = frozenset({
    "not", "no", "never", "n't", "cannot", "cant", "dont",
    "doesnt", "didnt", "wasnt", "isnt", "arent", "wouldnt",
    "couldnt", "shouldnt", "hardly", "barely",
    "don't", "doesn't", "didn't", "wasn't", "isn't", "aren't",
    "wouldn't", "couldn't", "shouldn't", "can't", "won't",
})


# ---------------------------------------------------------------------------
# Sentiment result model
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SentimentResult:
    """Sentiment analysis result for a single text.

    Attributes:
        text: The input text that was analyzed.
        compound: Normalized sentiment score from -1.0 (very negative) to +1.0 (very positive).
        positive: Fraction of text that is positive (0.0 to 1.0).
        negative: Fraction of text that is negative (0.0 to 1.0).
        neutral: Fraction of text that is neutral (0.0 to 1.0).
        label: Categorical label: "positive", "negative", or "neutral".
        word_count: Number of words analyzed.
    """

    text: str = ""
    compound: float = 0.0
    positive: float = 0.0
    negative: float = 0.0
    neutral: float = 1.0
    label: str = "neutral"
    word_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "compound": round(self.compound, 4),
            "positive": round(self.positive, 4),
            "negative": round(self.negative, 4),
            "neutral": round(self.neutral, 4),
            "label": self.label,
            "word_count": self.word_count,
        }


@dataclass(slots=True)
class CommentSentiment:
    """Sentiment analysis result for a single comment.

    Attributes:
        comment: The original comment.
        sentiment: The SentimentResult for the comment text.
    """

    comment: Comment
    sentiment: SentimentResult

    def to_dict(self) -> dict[str, Any]:
        d = self.comment.to_dict() if hasattr(self.comment, "to_dict") else {}
        d["sentiment"] = self.sentiment.to_dict()
        return d


@dataclass(slots=True)
class VideoSentiment:
    """Aggregate sentiment analysis for a video's comments.

    Attributes:
        video_id: The YouTube video ID.
        total_comments: Number of comments analyzed.
        positive_count: Number of positive comments.
        negative_count: Number of negative comments.
        neutral_count: Number of neutral comments.
        average_compound: Average compound score across all comments.
        overall_label: Aggregate sentiment label.
        comment_sentiments: Per-comment sentiment results.
    """

    video_id: str = ""
    total_comments: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    average_compound: float = 0.0
    overall_label: str = "neutral"
    comment_sentiments: list[CommentSentiment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "total_comments": self.total_comments,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "neutral_count": self.neutral_count,
            "average_compound": round(self.average_compound, 4),
            "overall_label": self.overall_label,
            "comment_sentiments": [cs.to_dict() for cs in self.comment_sentiments],
        }


# ---------------------------------------------------------------------------
# Core scoring logic
# ---------------------------------------------------------------------------

def analyze_sentiment(text: str) -> SentimentResult:
    """Analyze the sentiment of a text string.

    Uses a lexicon-based approach with negation and booster handling.
    No external dependencies required.

    Args:
        text: The text to analyze.

    Returns:
        A SentimentResult with compound score, proportions, and label.
    """
    if not text or not text.strip():
        return SentimentResult()

    # Tokenize — keep contractions for negator detection
    tokens = re.findall(r"[a-zA-Z']+|[!?]", text.lower())
    if not tokens:
        return SentimentResult(text=text)

    word_count = len([t for t in tokens if t.isalpha()])
    scores: list[float] = []
    pos_sum = 0.0
    neg_sum = 0.0

    for i, token in enumerate(tokens):
        if not token.isalpha():
            # Exclamation marks amplify sentiment
            if token == "!" and scores:
                scores[-1] *= 1.2
            continue

        # Check if previous word is a negator
        prev = tokens[i - 1].lower() if i > 0 else ""
        is_negated = prev in _NEGATORS

        # Check if previous word is a booster
        booster = _BOOSTERS.get(prev, 1.0)

        if token in _POSITIVE_WORDS:
            score = _POSITIVE_WORDS[token] * booster
            if is_negated:
                score = -score * 0.8  # negation reduces magnitude slightly
            scores.append(score)
            if score > 0:
                pos_sum += score
            else:
                neg_sum += abs(score)
        elif token in _NEGATIVE_WORDS:
            score = _NEGATIVE_WORDS[token] * booster
            if is_negated:
                score = -score * 0.8  # "not bad" → slightly positive
            scores.append(score)
            if score < 0:
                neg_sum += abs(score)
            else:
                pos_sum += score

    if not scores:
        return SentimentResult(text=text, neutral=1.0, label="neutral", word_count=word_count)

    # Normalize to [-1, 1]
    total = sum(abs(s) for s in scores)
    compound = sum(scores) / max(total, 1.0) if scores else 0.0

    # Clamp
    compound = max(-1.0, min(1.0, compound))

    # Proportions
    pos_prop = pos_sum / max(total, 1.0)
    neg_prop = neg_sum / max(total, 1.0)
    neu_prop = max(0.0, 1.0 - pos_prop - neg_prop)

    # Label based on compound score thresholds
    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"

    return SentimentResult(
        text=text,
        compound=compound,
        positive=pos_prop,
        negative=neg_prop,
        neutral=neu_prop,
        label=label,
        word_count=word_count,
    )


def analyze_comment_sentiment(comment: Comment) -> CommentSentiment:
    """Analyze sentiment of a single comment.

    Args:
        comment: A Comment model.

    Returns:
        A CommentSentiment with the original comment and sentiment result.
    """
    sentiment = analyze_sentiment(comment.text or "")
    return CommentSentiment(comment=comment, sentiment=sentiment)


def analyze_video_sentiment(result: VideoResult) -> VideoSentiment:
    """Analyze sentiment of all comments in a VideoResult.

    Args:
        result: A VideoResult with comments.

    Returns:
        A VideoSentiment with per-comment and aggregate sentiment.
    """
    comment_sentiments = []
    compounds: list[float] = []

    for comment in result.comments:
        cs = analyze_comment_sentiment(comment)
        comment_sentiments.append(cs)
        compounds.append(cs.sentiment.compound)

    total = len(comment_sentiments)
    pos_count = sum(1 for cs in comment_sentiments if cs.sentiment.label == "positive")
    neg_count = sum(1 for cs in comment_sentiments if cs.sentiment.label == "negative")
    neu_count = sum(1 for cs in comment_sentiments if cs.sentiment.label == "neutral")

    avg_compound = sum(compounds) / len(compounds) if compounds else 0.0

    if avg_compound >= 0.05:
        overall = "positive"
    elif avg_compound <= -0.05:
        overall = "negative"
    else:
        overall = "neutral"

    return VideoSentiment(
        video_id=result.video_id,
        total_comments=total,
        positive_count=pos_count,
        negative_count=neg_count,
        neutral_count=neu_count,
        average_compound=avg_compound,
        overall_label=overall,
        comment_sentiments=comment_sentiments,
    )
