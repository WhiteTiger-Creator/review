import os
import csv

def trim_ascii(s):
    # Trim leading and trailing ASCII whitespace (space, tab, carriage return, newline)
    return s.strip(" \t\r\n")

def normalize_account(acct_id):
    return trim_ascii(acct_id).lower()

def load_chart(chart_path):
    """
    Loads chart.tsv. Returns mapping of folded_account_id -> {canonical_id, normal_balance}
    Also returns a boolean indicating if there were duplicate chart IDs (case-insensitive).
    """
    chart = {}
    if not os.path.isfile(chart_path):
        return None, False
        
    try:
        with open(chart_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter='\t')
            header_skipped = False
            for row in reader:
                # Ignore blank lines
                if not row or all(trim_ascii(col) == "" for col in row):
                    continue
                if not header_skipped:
                    header_skipped = True
                    continue
                if len(row) < 4:
                    continue
                
                acct_id = trim_ascii(row[0])
                trim_ascii(row[1])
                trim_ascii(row[2])
                normal_bal = trim_ascii(row[3])
                
                if not acct_id:
                    continue
                    
                folded = acct_id.lower()
                if folded in chart:
                    return None, True # duplicate case-insensitive ID found
                    
                chart[folded] = {
                    "canonical": acct_id,
                    "normal_balance": normal_bal
                }
    except Exception:
        return None, False
        
    return chart, False

def parse_journal_line(row_data):
    """
    Parses a single row from the CSV.
    We trim leading/trailing ASCII whitespace from account_id, debit_cents, and credit_cents.
    """
    if len(row_data) < 5:
        return None
    return {
        "posting_date": trim_ascii(row_data[0]),
        "account_id": trim_ascii(row_data[1]),
        "debit_cents": trim_ascii(row_data[2]),
        "credit_cents": trim_ascii(row_data[3]),
        "memo": row_data[4]
    }
