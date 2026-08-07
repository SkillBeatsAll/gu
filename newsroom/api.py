from django.http import JsonResponse
from django.urls import reverse

from . import models


def _serialise(rows, request):
    """Turn [[slug, title], ...] into a list of JSON-ready dicts."""
    articles = []
    for row in rows or []:
        if len(row) < 2:
            continue
        slug = row[0].strip()
        # Rejoin: titles may legitimately contain a pipe.
        title = "|".join(row[1:]).strip()
        if not slug or not title:
            continue
        articles.append(
            {
                "slug": slug,
                "title": title,
                "url": request.build_absolute_uri(
                    reverse("newsroom:article.detail", args=[slug])
                ),
            }
        )
    return articles


def most_popular(request):
    """Public, unauthenticated JSON feed of the current most-popular list."""
    articles = _serialise(models.MostPopular.get_most_popular_list(), request)
    return JsonResponse({"count": len(articles), "articles": articles})


def most_deeply_read(request):
    """Public, unauthenticated JSON feed of the current most-deeply-read list."""
    articles = _serialise(models.MostDeeplyRead.get_list(), request)
    return JsonResponse({"count": len(articles), "articles": articles})
