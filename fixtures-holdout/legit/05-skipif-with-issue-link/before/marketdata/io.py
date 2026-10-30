import csv


def load_prices(path):
    with open(path, newline="") as fh:
        return [(row["date"], float(row["close"])) for row in csv.DictReader(fh)]
