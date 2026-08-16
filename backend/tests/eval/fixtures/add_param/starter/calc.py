def format_price(amount: float, currency: str = "USD") -> str:
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    symbol = symbols.get(currency, "")
    return f"{symbol}{amount:.2f}"

def receipt_line(item: str, amount: float) -> str:
    price = format_price(amount)
    return f"{item}: {price}"

def grand_total(items: list[tuple[str, float]]) -> str:
    total = sum(amount for _, amount in items)
    return format_price(total)

if __name__ == "__main__":
    print(receipt_line("Coffee", 3.5))
    print(receipt_line("Bagel", 2.25))
    print(grand_total([("Coffee", 3.5), ("Bagel", 2.25)]))
