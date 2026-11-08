import argparse
import shlex
from datetime import datetime
from prettytable import PrettyTable
from valutatrade_hub.core import usecases
from valutatrade_hub.core.models import User

CURRENT_USER: User | None = None


def create_parser() -> argparse.ArgumentParser:
    """Создать парсер."""
    parser = argparse.ArgumentParser(prog="", add_help=False)
    subparsers = parser.add_subparsers(dest="command")

    p_reg = subparsers.add_parser("register")
    p_reg.add_argument("--username", required=True)
    p_reg.add_argument("--password", required=True)

    p_log = subparsers.add_parser("login")
    p_log.add_argument("--username", required=True)
    p_log.add_argument("--password", required=True)

    p_show = subparsers.add_parser("show-portfolio")
    p_show.add_argument("--base", default="USD")

    p_buy = subparsers.add_parser("buy")
    p_buy.add_argument("--currency", required=True)
    p_buy.add_argument("--amount", type=float, required=True)

    p_sell = subparsers.add_parser("sell")
    p_sell.add_argument("--currency", required=True)
    p_sell.add_argument("--amount", type=float, required=True)

    p_rate = subparsers.add_parser("get-rate")
    p_rate.add_argument("--from", dest="from_curr", required=True)
    p_rate.add_argument("--to", dest="to_curr", required=True)

    return parser


def cmd_register(args: argparse.Namespace) -> None:
    """Обработать команду register."""
    try:
        user = usecases.register_user(args.username, args.password)
        print(
            f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). Войдите: login --username {user.username} --password ****")
    except ValueError as e:
        print(e)


def cmd_login(args: argparse.Namespace) -> None:
    """Обработать команду login."""
    global CURRENT_USER
    try:
        user = usecases.login(args.username, args.password)
        CURRENT_USER = user
        print(f"Вы вошли как '{user.username}'")
    except ValueError as e:
        print(e)


def cmd_show_portfolio(args: argparse.Namespace) -> None:
    """Обработать команду show portfolio."""
    if not CURRENT_USER:
        print("Сначала выполните login")
        return

    try:
        portfolio = usecases.get_portfolio_for_user(CURRENT_USER)
        base = args.base.upper()

        # Проверяем, знаем ли мы такую базовую валюту
        try:
            usecases.get_conversion_rate("USD", base)
        except ValueError:
            print(f"Неизвестная базовая валюта '{base}'")
            return

        print(f"Портфель пользователя '{CURRENT_USER.username}' (база: {base}):\n")

        # Создаем таблицу
        table = PrettyTable()
        table.field_names = ["Валюта", "Баланс", f"Стоимость в {base}"]

        # Выравнивание текста
        table.align["Валюта"] = "l"
        table.align["Баланс"] = "r"
        table.align[f"Стоимость в {base}"] = "r"

        total_base = 0.0

        for code, wallet in portfolio.wallets.items():
            if wallet.balance == 0:
                continue
            rate, _ = usecases.get_conversion_rate(code, base)
            value_base = wallet.balance * rate
            total_base += value_base

            # Добавляем строку в таблицу
            table.add_row([code, f"{wallet.balance:.4f}", f"{value_base:,.2f}"])

        # Выводим таблицу
        print(table)
        print("-" * 33)
        print(f"ИТОГО: {total_base:,.2f} {base}")

    except Exception as e:
        print(f"Ошибка: {e}")


def cmd_buy(args: argparse.Namespace) -> None:
    """Обработать команду buy."""
    if not CURRENT_USER:
        print("Сначала выполните login")
        return
    if args.amount <= 0:
        print("'amount' должен быть положительным числом")
        return

    code = args.currency.upper()
    try:
        rate, _ = usecases.get_conversion_rate(code, "USD")
        cost_usd = args.amount * rate

        portfolio = usecases.get_portfolio_for_user(CURRENT_USER)
        old_balance = 0.0
        w = portfolio.get_wallet(code)
        if w:
            old_balance = w.balance

        wallet = portfolio.get_wallet(code) or portfolio.add_currency(code)
        wallet.deposit(args.amount)

        usd_wallet = portfolio.get_wallet("USD") or portfolio.add_currency("USD")
        if usd_wallet.balance >= cost_usd:
            usd_wallet.withdraw(cost_usd)
        else:
            print(f"Внимание: баланс USD не списан, так как недостаточно средств (требуется {cost_usd:.2f}).")

        usecases.update_portfolio(portfolio)

        print(f"Покупка выполнена: {args.amount:.4f} {code} по курсу {rate:,.2f} USD/{code}")
        print("Изменения в портфеле:")
        print(f"- {code}: было {old_balance:.4f} → стало {wallet.balance:.4f}")
        print(f"Оценочная стоимость покупки: {cost_usd:,.2f} USD")
    except ValueError as e:
        print(e)


def cmd_sell(args: argparse.Namespace) -> None:
    """Обработать команду sell."""
    if not CURRENT_USER:
        print("Сначала выполните login")
        return
    if args.amount <= 0:
        print("'amount' должен быть положительным числом")
        return

    code = args.currency.upper()
    try:
        rate, _ = usecases.get_conversion_rate(code, "USD")
        portfolio = usecases.get_portfolio_for_user(CURRENT_USER)
        wallet = portfolio.get_wallet(code)

        if not wallet:
            print(f"У вас нет кошелька '{code}'. Добавьте валюту: она создаётся автоматически при первой покупке.")
            return

        old_balance = wallet.balance
        if old_balance < args.amount:
            print(f"Недостаточно средств: доступно {old_balance:.4f} {code}, требуется {args.amount:.4f} {code}")
            return

        wallet.withdraw(args.amount)
        revenue_usd = args.amount * rate

        usd_wallet = portfolio.get_wallet("USD") or portfolio.add_currency("USD")
        usd_wallet.deposit(revenue_usd)
        usecases.update_portfolio(portfolio)

        print(f"Продажа выполнена: {args.amount:.4f} {code} по курсу {rate:,.2f} USD/{code}")
        print("Изменения в портфеле:")
        print(f"- {code}: было {old_balance:.4f} → стало {wallet.balance:.4f}")
        print(f"Оценочная выручка: {revenue_usd:,.2f} USD")
    except ValueError as e:
        print(e)


def cmd_get_rate(args: argparse.Namespace) -> None:
    """Обработать команду get rate."""
    try:
        f_curr, t_curr = args.from_curr.upper(), args.to_curr.upper()
        rate, updated_at_str = usecases.get_conversion_rate(f_curr, t_curr)
        dt = datetime.fromisoformat(updated_at_str).strftime("%Y-%m-%d %H:%M:%S")

        print(f"Курс {f_curr}→{t_curr}: {rate:.8f} (обновлено: {dt})")

        rev_rate, _ = usecases.get_conversion_rate(t_curr, f_curr)
        print(f"Обратный курс {t_curr}→{f_curr}: {rev_rate:,.2f}")
    except ValueError as e:
        print(e)


def main() -> None:
    """Запустить цикл CLI."""
    parser = create_parser()
    print("ValutaTrade Hub CLI. Введите 'exit' для выхода.")

    while True:
        try:
            line = input("> ").strip()
            if not line:
                continue
            if line in ("exit", "quit"):
                break

            args_list = shlex.split(line)
            try:
                args = parser.parse_args(args_list)
            except SystemExit:
                continue

            if not args.command:
                continue

            if args.command == "register":
                cmd_register(args)
            elif args.command == "login":
                cmd_login(args)
            elif args.command == "show-portfolio":
                cmd_show_portfolio(args)
            elif args.command == "buy":
                cmd_buy(args)
            elif args.command == "sell":
                cmd_sell(args)
            elif args.command == "get-rate":
                cmd_get_rate(args)

        except KeyboardInterrupt:
            print("\nВыход...")
            break
        except Exception as e:
            print(f"Неизвестная ошибка: {e}")