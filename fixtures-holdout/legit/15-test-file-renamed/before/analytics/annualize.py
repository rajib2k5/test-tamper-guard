def annualize(daily_return, days=252):
    return (1 + daily_return) ** days - 1
