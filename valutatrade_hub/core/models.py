from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Any


class User:
    """Пользователь системы."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        """Создать пользователя из уже хешированного пароля."""
        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        """ID пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        """Установить имя пользователя."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым.")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        """Хеш пароля."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Соль пароля."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Дата регистрации."""
        return self._registration_date

    @classmethod
    def create_new(
        cls, user_id: int, username: str, password: str
    ) -> "User":
        """Создать нового пользователя."""
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов.")
        salt = secrets.token_hex(8)
        hashed = cls._hash_password(password, salt)
        return cls(user_id, username, hashed, salt, datetime.now())

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """Вычислить sha256"""
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Проверить, что введённый пароль совпадает с сохранённым хешем."""
        return self._hash_password(password, self._salt) == self._hashed_password

    def change_password(self, new_password: str) -> None:
        """Сменить пароль с пересчётом хеша."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов.")
        self._hashed_password = self._hash_password(new_password, self._salt)

    def get_user_info(self) -> dict[str, Any]:
        """Информация о пользователе без пароля и соли."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Сериализация для сохранения в JSON."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    def __repr__(self) -> str:
        """Строковое представление."""
        return f"User(id={self._user_id}, username={self._username!r})"


class Wallet:
    """Кошелёк пользователя для одной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        """Создать кошелёк для указанной валюты."""
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым.")
        self.currency_code = currency_code.upper().strip()
        self._balance = 0.0
        self.balance = balance

    @property
    def balance(self) -> float:
        """Текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """Установить баланс."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом.")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным.")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Пополнить баланс на положительную сумму."""
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("Сумма должна быть числом.")
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной.")
        self.balance = self._balance + float(amount)

    def withdraw(self, amount: float) -> None:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("Сумма должна быть числом.")
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной.")
        if amount > self._balance:
            raise ValueError(
                f"Недостаточно средств: баланс {self._balance}, "
                f"запрошено {amount}."
            )
        self.balance = self._balance - float(amount)

    def get_balance_info(self) -> dict[str, Any]:
        """Информация о текущем балансе."""
        return {"currency_code": self.currency_code, "balance": self._balance}

    def to_dict(self) -> dict[str, Any]:
        """Сериализация кошелька для JSON."""
        return {"currency_code": self.currency_code, "balance": self._balance}

    def __repr__(self) -> str:
        """Строковое представление."""
        return f"Wallet({self.currency_code}, {self._balance})"


class Portfolio:
    """Набор кошельков одного пользователя."""

    def __init__(
        self,
        user: User,
        wallets: dict[str, Wallet] | None = None,
    ) -> None:
        """Создать портфель для пользователя."""
        self._user = user
        self._user_id = user.user_id
        self._wallets: dict[str, Wallet] = wallets or {}

    @property
    def user(self) -> User:
        return self._user

    @property
    def user_id(self) -> int:
        """Идентификатор владельца портфеля."""
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Копия словаря кошельков."""
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавить новый кошелёк в портфель."""
        code = currency_code.upper().strip()
        if code in self._wallets:
            raise ValueError(f"Валюта {code} уже есть в портфеле.")
        wallet = Wallet(code)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Вернуть кошелёк по коду валюты или None."""
        return self._wallets.get(currency_code.upper().strip())

    def get_total_value(
        self,
        base_currency: str = "USD",
        exchange_rates: dict[str, float] | None = None,
    ) -> float:
        """Суммарная стоимость всех валют в базовой валюте."""
        from .utils import DEFAULT_EXCHANGE_RATES

        rates = exchange_rates or DEFAULT_EXCHANGE_RATES
        base_rate = rates.get(base_currency.upper(), 1.0)
        total = 0.0
        for code, wallet in self._wallets.items():
            rate = rates.get(code, 1.0)
            total += wallet.balance * rate / base_rate
        return total

    def to_dict(self) -> dict[str, Any]:
        """Сериализация портфеля для JSON."""
        return {
            "user_id": self._user_id,
            "wallets": {
                code: {"balance": w.balance}
                for code, w in self._wallets.items()
            },
        }

    def __repr__(self) -> str:
        """Строковое представление."""
        return f"Portfolio(user_id={self._user_id}, wallets={list(self._wallets)})"