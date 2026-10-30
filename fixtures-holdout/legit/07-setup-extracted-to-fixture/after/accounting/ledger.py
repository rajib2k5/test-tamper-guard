class Ledger:
    def __init__(self):
        self.entries = []

    def post(self, account, amount):
        self.entries.append((account, amount))

    def balance(self, account):
        return sum(a for acc, a in self.entries if acc == account)

    def total(self):
        return sum(a for _, a in self.entries)
