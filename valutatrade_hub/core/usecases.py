from __future__ import annotations

from datetime import datetime

from . import utils
from .models import Portfolio, User, Wallet


def load_users() -> list[User]:
    """Загрузить список пользователей из JSON."""
    raw = utils.load_json(utils.USERS_FILE, [])
    users: list[User] = []
    for item in raw:
        users.append(
            User(
                user_id=item["user_id"],
                username=item["username"],
                hashed_password=item["hashed_password"],
                salt=item["salt"],
                registration_date=datetime.fromisoformat(item["registration_date"]),
            )
        )
    return users


def save_users(users: list[User]) -> None:
    """Сохранить список пользователей в JSON."""
    utils.save_json(utils.USERS_FILE, [u.to_dict() for u in users])


def register_user(username: str, password: str) -> User:
    """Зарегистрировать пользователя и создать пустой портфель."""
    users = load_users()
    if any(u.username == username for u in users):
        raise ValueError(f"Пользователь {username!r} уже существует.")
    next_id = max((u.user_id for u in users), default=0) + 1
    user = User.create_new(next_id, username, password)
    users.append(user)
    save_users(users)

    portfolios = load_portfolios()
    portfolios.append(Portfolio(user))
    save_portfolios(portfolios)
    return user


def login(username: str, password: str) -> User:
    """Проверить учётные данные и вернуть пользователя."""
    for user in load_users():
        if user.username == username and user.verify_password(password):
            return user
    raise ValueError("Неверное имя пользователя или пароль.")


def load_portfolios() -> list[Portfolio]:
    """Загрузить портфели из JSON."""
    users_by_id = {u.user_id: u for u in load_users()}
    raw = utils.load_json(utils.PORTFOLIOS_FILE, [])
    portfolios: list[Portfolio] = []
    for item in raw:
        user = users_by_id.get(item["user_id"])
        if user is None:
            continue
        wallets: dict[str, Wallet] = {}
        for code, w in item.get("wallets", {}).items():
            wallets[code] = Wallet(code, w.get("balance", 0.0))
        portfolios.append(Portfolio(user, wallets))
    return portfolios


def save_portfolios(portfolios: list[Portfolio]) -> None:
    """Сохранить портфели в JSON."""
    utils.save_json(
        utils.PORTFOLIOS_FILE,
        [p.to_dict() for p in portfolios],
    )


def get_portfolio_for_user(user: User) -> Portfolio:
    """Вернуть портфель пользователя."""
    for p in load_portfolios():
        if p.user_id == user.user_id:
            return p
    raise ValueError(f"Портфель пользователя {user.user_id} не найден.")


def update_portfolio(portfolio: Portfolio) -> None:
    """Обновить портфель пользователя в хранилище."""
    portfolios = load_portfolios()
    for i, p in enumerate(portfolios):
        if p.user_id == portfolio.user_id:
            portfolios[i] = portfolio
            break
    save_portfolios(portfolios)


@utils.log_action
def deposit(user: User, currency_code: str, amount: float) -> Wallet:
    """Пополнить кошелёк."""
    portfolio = get_portfolio_for_user(user)
    code = currency_code.upper().strip()
    wallet = portfolio.get_wallet(code) or portfolio.add_currency(code)
    wallet.deposit(amount)
    update_portfolio(portfolio)
    return wallet


@utils.log_action
def withdraw(user: User, currency_code: str, amount: float) -> Wallet:
    """Снять средства с кошелька."""
    portfolio = get_portfolio_for_user(user)
    code = currency_code.upper().strip()
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        raise ValueError(f"Нет кошелька для валюты {code}.")
    wallet.withdraw(amount)
    update_portfolio(portfolio)
    return wallet


@utils.cached(ttl_seconds=30)
def get_rates() -> dict[str, float]:
    """Вернуть актуальные курсы валют."""
    return utils.load_json(utils.RATES_FILE, utils.DEFAULT_EXCHANGE_RATES)


@utils.log_action
def buy_currency(user: User, target_code: str, amount: float) -> Wallet:
    """Купить за USD по курсу."""
    target = target_code.upper().strip()
    if target == "USD":
        raise ValueError("Покупка USD за USD не имеет смысла.")
    rates = get_rates()
    if target not in rates:
        raise ValueError(f"Нет курса для валюты {target}.")
    cost_usd = amount * rates[target]

    portfolio = get_portfolio_for_user(user)
    usd_wallet = portfolio.get_wallet("USD")
    if usd_wallet is None:
        raise ValueError("У пользователя нет USD-кошелька.")
    usd_wallet.withdraw(cost_usd)

    target_wallet = portfolio.get_wallet(target) or portfolio.add_currency(target)
    target_wallet.deposit(amount)
    update_portfolio(portfolio)
    return target_wallet


@utils.log_action
def sell_currency(user: User, source_code: str, amount: float) -> Wallet:
    """Продать и получить USD."""
    source = source_code.upper().strip()
    if source == "USD":
        raise ValueError("Продавать USD за USD не имеет смысла.")
    rates = get_rates()
    if source not in rates:
        raise ValueError(f"Нет курса для валюты {source}.")

    portfolio = get_portfolio_for_user(user)
    source_wallet = portfolio.get_wallet(source)
    if source_wallet is None:
        raise ValueError(f"Нет кошелька для валюты {source}.")
    source_wallet.withdraw(amount)

    usd_wallet = portfolio.get_wallet("USD") or portfolio.add_currency("USD")
    usd_wallet.deposit(amount * rates[source])
    update_portfolio(portfolio)
    return usd_wallet