import csv
from datetime import datetime

class FinanceManager:
    def __init__(self):
        pass

    def import_csv(self, filepath):
        with open(filepath, 'r') as file:
            reader = csv.reader(file)
            transactions = []
            for row in reader:
                date = datetime.strptime(row[0], '%Y-%m-%d')
                libelle = row[1]
                montant = float(row[2])
                categorie = row[3]
                transactions.append({
                    'date': date,
                    'libelle': libelle,
                    'montant': montant,
                    'categorie': categorie
                })
            return transactions

    def get_balance(self, transactions):
        total = 0
        for transaction in transactions:
            total += transaction['montant']
        return total

    def get_expenses_by_category(self, transactions):
        categories = {}
        for transaction in transactions:
            categorie = transaction['categorie']
            if categorie not in categories:
                categories[categorie] = []
            categories[categorie].append(transaction)
        return categories

    def get_summary(self, transactions):
        revenus = 0
        depenses = 0
        solde = 0
        for transaction in transactions:
            if transaction['categorie'] == 'Revenus':
                revenus += transaction['montant']
            else:
                depenses += transaction['montant']
        solde = revenus - depenses
        return f"Revenus : {revenus}\nDépenses : {depenses}\nSolde : {solde}"

    def get_total_expenses_by_category(self, transactions):
        categories = {}
        for transaction in transactions:
            categorie = transaction['categorie']
            if categorie not in categories:
                categories[categorie] = 0
            categories[categorie] += transaction['montant']
        return categories

    def save_transactions_to_csv(self, filepath, transactions):
        with open(filepath, 'w') as file:
            writer = csv.writer(file)
            for transaction in transactions:
                writer.writerow([
                    transaction['date'].strftime('%Y-%m-%d'),
                    transaction['libelle'],
                    transaction['montant'],
                    transaction['categorie']
                ])
