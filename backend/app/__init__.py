import itertools
import logging
from pathlib import Path

from flask import Flask, request
import redis
import rq

from app.provider import build_url, get_provider, parse_url_as_provider_and_book_id
from app.translator import get_default_translator
from app.cache import BookCache
from app.model import BookMetadata, TocEpisodeToken
from app.make import make_book

logging.basicConfig(
    level=logging.INFO,
)

redis_connection = redis.Redis(host="redis", port=6379, db=0)
queue = rq.Queue(connection=redis_connection)

books_path = Path("/books")


def update_book(provider_id: str, book_id: str, lang: str):
    provider = get_provider(provider_id)

    cache = BookCache(
        cache_path=books_path / f"{provider_id}.{book_id}.zip",
    )

    book = provider.get_book(
        book_id=book_id,
        cache=cache,
    )

    make_book(
        output_path=books_path,
        book=book,
    )

    if lang != provider.lang:
        translator = get_default_translator()

        book_translated = translator.translate_book(
            book=book,
            lang=lang,
            cache=cache,
        )

        make_book(
            output_path=books_path,
            book=book_translated,
            secondary_book=book,
        )


def get_status(job_id: str) -> str | None:
    job = queue.fetch_job(job_id=job_id)
    if not job:
        return None

    status = job.get_status(refresh=True)
    if status in ["queued", "started", "failed"]:
        return status
    else:
        return "unknown"


def get_book(
    url: str,
    provider_id: str,
    book_id: str,
    metadata: BookMetadata,
    cache: BookCache,
):
    total_episode_number = sum(
        [1 for token in metadata.toc if isinstance(token, TocEpisodeToken)]
    )

    book_file_groups = []
    for lang in ["jp", "zh"]:
        cached_episode_number = cache.count_episode(lang)

        book_file_group = {
            "lang": lang,
            "status": None,
            "total_episode_number": total_episode_number,
            "cached_episode_number": cached_episode_number,
            "files": [],
        }

        possible_suffixes = ["txt", "epub"]
        if lang == "zh":
            possible_suffixes.append("mixed.epub")

        suffix_to_type = {
            "txt": "TXT",
            "epub": "EPUB",
            "mixed.epub": "EPUB原文混合版",
        }

        for suffix in possible_suffixes:
            book_type = suffix_to_type[suffix]
            book_name = f"{provider_id}.{book_id}.{lang}.{suffix}"
            book_path = books_path / book_name
            if not book_path.exists():
                book_name = None
            book_file_group["files"].append({"type": book_type, "filename": book_name})

        book_file_groups.append(book_file_group)

    return {
        "url": url,
        "provider_id": provider_id,
        "book_id": book_id,
        "title": metadata.title,
        "files": book_file_groups,
    }


def create_app():
    app = Flask(__name__)

    @app.get("/query")
    def _query():
        url = request.args.get("url")
        if url is None:
            return "没有url参数", 400
        parsed = parse_url_as_provider_and_book_id(url)
        if parsed is None:
            logging.info("无法解析网址: %s", url)
            return "无法解析网址，可能是因为格式错误或者不支持", 400

        provider, book_id = parsed

        cache = BookCache(
            cache_path=books_path / f"{provider.provider_id}.{book_id}.zip",
        )

        try:
            metadata = provider.get_book_metadata(
                book_id=book_id,
                cache=cache,
            )
        except Exception:
            return "获取元数据失败。", 500

        book = get_book(
            url=provider.build_url_from_book_id(book_id=book_id),
            provider_id=provider.provider_id,
            book_id=book_id,
            metadata=metadata,
            cache=cache,
        )

        for group in book["files"]:
            group["status"] = get_status(
                job_id="/".join([provider.provider_id, book_id, group["lang"]])
            )

        return book

    @app.get("/list")
    def _list():
        next_id = request.args.get("next")
        page_size = 60
        all_zip_paths = sorted(
            books_path.glob("*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if next_id:
            paged_zip_paths = itertools.islice(
                itertools.dropwhile(lambda p: p.stem != next_id, all_zip_paths),
                start=1,
                stop=page_size + 1,
            )
        else:
            paged_zip_paths = all_zip_paths[:page_size]

        books = []
        for zip_path in paged_zip_paths:
            try:
                provider_id, book_id = zip_path.stem.split(".")
            except ValueError:
                continue

            cache = BookCache(zip_path)
            metadata = cache.get_book_metadata("jp")

            if not metadata:
                continue

            book = get_book(
                url=build_url(provider_id=provider_id, book_id=book_id),
                provider_id=provider_id,
                book_id=book_id,
                metadata=metadata,
                cache=cache,
            )

            books.append(book)

        return books

    @app.post("/book-update")
    def _create_book_update_job():
        provider_id = request.json.get("provider_id")
        if not provider_id:
            return "没有provider_id参数", 400

        book_id = request.json.get("book_id")
        if not book_id:
            return "没有book_id参数", 400

        lang = request.json.get("lang")
        if not lang:
            return "没有lang参数", 400

        if queue.count >= 100:
            return "更新任务数目已达上限100", 500

        job_id = "/".join([provider_id, book_id, lang])

        if queue.fetch_job(job_id=job_id):
            return "更新任务已经在队列中", 500

        queue.enqueue(
            update_book,
            provider_id,
            book_id,
            lang,
            ttl=-1,
            result_ttl=0,
            failure_ttl=0,
            job_id=job_id,
        )

        return "成功添加更新任务"

    return app
