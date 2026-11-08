from __future__ import annotations

from datetime import datetime, timedelta

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
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    if not isinstance(password, str) or len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

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
        if user.username == username:
            if user.verify_password(password):
                return user
            raise ValueError("Неверный пароль")
    raise ValueError(f"Пользователь '{username}' не найден")


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
        raise ValueError(
            f"У вас нет кошелька '{code}'. Добавьте валюту: она создаётся автоматически при первой покупке.")
    wallet.withdraw(amount)
    update_portfolio(portfolio)
    return wallet


def get_conversion_rate(from_curr: str, to_curr: str) -> tuple[float, str]:
    """Получить курс конвертации."""
    from_curr = from_curr.upper()
    to_curr = to_curr.upper()

    if from_curr == to_curr:
        return 1.0, datetime.now().isoformat()

    rates_data = utils.load_json(utils.RATES_FILE, {})
    pair = f"{from_curr}_{to_curr}"
    reverse_pair = f"{to_curr}_{from_curr}"

    rate_info = rates_data.get(pair)

    if not rate_info and reverse_pair in rates_data:
        rev_info = rates_data[reverse_pair]
        rate = 1.0 / rev_info["rate"]
        return rate, rev_info["updated_at"]

    if rate_info:
        updated_at = datetime.fromisoformat(rate_info["updated_at"])
        if datetime.now() - updated_at < timedelta(minutes=5):
            return rate_info["rate"], rate_info["updated_at"]

    mock_rates = {"USD": 1.0, "EUR": 1.08, "BTC": 59300.0, "ETH": 3720.0, "RUB": 0.01016}
    if from_curr in mock_rates and to_curr in mock_rates:
        rate = mock_rates[from_curr] / mock_rates[to_curr]
        now_iso = datetime.now().isoformat()

        rates_data[pair] = {"rate": rate, "updated_at": now_iso}
        rates_data["source"] = "ParserService (Mock)"
        rates_data["last_refresh"] = now_iso
        utils.save_json(utils.RATES_FILE, rates_data)
        return rate, now_iso

    raise ValueError(f"Курс {from_curr}→{to_curr} недоступен. Повторите попытку позже.")


@utils.log_action
def buy_currency(user: User, target_code: str, amount: float) -> Wallet:
    """Купить за USD по курсу."""
    target = target_code.upper().strip()
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    if target == "USD":
        raise ValueError("Покупка USD за USD не имеет смысла.")

    try:
        rate, _ = get_conversion_rate(target, "USD")
    except ValueError:
        raise ValueError(f"Не удалось получить курс для {target}→USD")

    cost_usd = amount * rate

    portfolio = get_portfolio_for_user(user)
    usd_wallet = portfolio.get_wallet("USD") or portfolio.add_currency("USD")

    if usd_wallet.balance < cost_usd:
        raise ValueError(f"Недостаточно средств: доступно {usd_wallet.balance:.2f} USD, требуется {cost_usd:.2f} USD")

    usd_wallet.withdraw(cost_usd)

    target_wallet = portfolio.get_wallet(target) or portfolio.add_currency(target)
    target_wallet.deposit(amount)
    update_portfolio(portfolio)
    return target_wallet


@utils.log_action
def sell_currency(user: User, source_code: str, amount: float) -> Wallet:
    """Продать и получить USD."""
    source = source_code.upper().strip()
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    if source == "USD":
        raise ValueError("Продавать USD за USD не имеет смысла.")

    try:
        rate, _ = get_conversion_rate(source, "USD")
    except ValueError:
        raise ValueError(f"Не удалось получить курс для {source}→USD")

    portfolio = get_portfolio_for_user(user)
    source_wallet = portfolio.get_wallet(source)
    if source_wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{source}'. Добавьте валюту: она создаётся автоматически при первой покупке.")

    if source_wallet.balance < amount:
        raise ValueError(
            f"Недостаточно средств: доступно {source_wallet.balance:.4f} {source}, требуется {amount:.4f} {source}")

    source_wallet.withdraw(amount)

    usd_wallet = portfolio.get_wallet("USD") or portfolio.add_currency("USD")
    usd_wallet.deposit(amount * rate)
    update_portfolio(portfolio)
    return usd_wallet