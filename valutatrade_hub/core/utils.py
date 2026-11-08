from __future__ import annotations

import functools
import hashlib
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
USERS_FILE = DATA_DIR / "users.json"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"
RATES_FILE = DATA_DIR / "rates.json"

DEFAULT_EXCHANGE_RATES: dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.1,
    "BTC": 60_000.0,
    "ETH": 3_000.0,
}


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    defaults = {
        USERS_FILE: [],
        PORTFOLIOS_FILE: [],
        RATES_FILE: DEFAULT_EXCHANGE_RATES,
    }
    for path, default in defaults.items():
        if not path.exists():
            path.write_text(
                json.dumps(default, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )


def load_json(path: Path, default: Any = None) -> Any:
    """Прочитать JSON файл, вернуть default при ошибке или отсутствии."""
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def save_json(path: Path, data: Any) -> None:
    """Записать данные в JSON файл."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def hash_password(password: str, salt: str) -> str:
    """Вычислить sha256."""
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


logger = logging.getLogger(__name__)


def log_action(func: Callable[..., Any]) -> Callable[..., Any]:
    """Декоратор для логирования."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.info("→ %s", func.__name__)
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            logger.error("✖ %s: %s", func.__name__, exc)
            raise
        logger.info("✓ %s", func.__name__)
        return result

    return wrapper


def with_confirmation(func: Callable[..., Any]) -> Callable[..., Any]:
    """Декоратор для подтверждения перед вызовом функции."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        answer = input(f"Подтвердить {func.__name__}? [y/N]: ").strip().lower()
        if answer != "y":
            print("Отменено.")
            return None
        return func(*args, **kwargs)

    return wrapper


def cached(ttl_seconds: int = 60) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Декоратор для кэширования функции"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cache: dict[Any, tuple[Any, float]] = {}

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in cache:
                value, ts = cache[key]
                if now - ts < ttl_seconds:
                    return value
            result = func(*args, **kwargs)
            cache[key] = (result, now)
            return result

        return wrapper

    return decorator