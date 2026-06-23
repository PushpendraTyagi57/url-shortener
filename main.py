import os
import redis
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from dotenv import load_dotenv

from database import engine, get_db, Base
from models import URL

load_dotenv()

#Setup
Base.metadata.create_all(bind=engine)

redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    decode_responses=True
)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="URL Shortener")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

#Helpers
def encode_base62(num: int) -> str:
    if num == 0:
        return BASE62[0]
    result = []
    while num:
        result.append(BASE62[num % 62])
        num //= 62
    return "".join(reversed(result))

#Schemas
class ShortenRequest(BaseModel):
    long_url: HttpUrl

class ShortenResponse(BaseModel):
    short_url:  str
    short_code: str
    long_url:   str

#Routes
@app.post("/shorten", response_model=ShortenResponse, status_code=201)
@limiter.limit("10/minute")
def shorten_url(request: Request, body: ShortenRequest, db: Session = Depends(get_db)):
    long_url = str(body.long_url)

    # Check if URL already exists
    existing = db.query(URL).filter(URL.long_url == long_url).first()
    if existing:
        return ShortenResponse(
            short_url=f"{BASE_URL.rstrip('/')}/{existing.short_code}",
            short_code=existing.short_code,
            long_url=existing.long_url,
        )

    url_entry = URL(long_url=long_url, short_code="pending")
    db.add(url_entry)
    db.flush()

    url_entry.short_code = encode_base62(url_entry.id)
    db.commit()
    db.refresh(url_entry)

    redis_client.setex(url_entry.short_code, 604800, long_url)

    return ShortenResponse(
        short_url=f"{BASE_URL.rstrip('/')}/{url_entry.short_code}",
        short_code=url_entry.short_code,
        long_url=long_url,
    )


@app.get("/stats/{short_code}")
def get_stats(short_code: str, db: Session = Depends(get_db)):
    url_entry = db.query(URL).filter(URL.short_code == short_code).first()
    if not url_entry:
        raise HTTPException(status_code=404, detail="Short URL not found")

    return {
        "short_code":  url_entry.short_code,
        "long_url":    url_entry.long_url,
        "click_count": url_entry.click_count,
        "created_at":  url_entry.created_at,
    }


@app.get("/{short_code}")
@limiter.limit("60/minute")
def redirect_to_long_url(short_code: str, request: Request, db: Session = Depends(get_db)):
    cached_url = redis_client.get(short_code)
    if cached_url:
        db.query(URL).filter(URL.short_code == short_code).update(
            {URL.click_count: URL.click_count + 1}
        )
        db.commit()
        return RedirectResponse(url=cached_url, status_code=301)

    url_entry = db.query(URL).filter(URL.short_code == short_code).first()
    if not url_entry:
        raise HTTPException(status_code=404, detail="Short URL not found")

    redis_client.setex(short_code, 604800, url_entry.long_url)
    url_entry.click_count += 1
    db.commit()

    return RedirectResponse(url=url_entry.long_url, status_code=301)