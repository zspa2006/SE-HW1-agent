def total_price(prices: list[float], discount: float = 0.0) -> float:
    """Return the discounted sum of a list of prices."""
    subtotal = sum(prices)
    return round(subtotal * (1 - discount), 2)


if __name__ == "__main__":
    print(total_price([20.0, 30.0], discount=0.1))
