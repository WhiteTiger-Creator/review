import sys
import json
import argparse
import csv
from pathlib import Path
from ledger import load_chart, parse_journal_line, normalize_account

def in_window(date_str, start, end):
    return start <= date_str <= end

def is_non_negative_integer(val):
    return val.isdigit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--postings", required=True)
    parser.add_argument("--accounts", required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--snapshot", required=True)
    args = parser.parse_args()

    chart, has_dupes = load_chart(args.accounts)
    if has_dupes:
        # Duplicate chart IDs: write empty snapshot and exit 1
        with open(args.snapshot, "w", encoding="utf-8") as f:
            pass
        sys.exit(1)
        
    if chart is None:
        sys.exit(2)

    try:
        with open(args.window, "r", encoding="utf-8") as f:
            win = json.load(f)
            start_date = win.get("start_date")
            end_date = win.get("end_date")
    except Exception:
        sys.exit(2)

    if not start_date or not end_date:
        sys.exit(2)

    debit_sums = {}
    credit_sums = {}
    
    unknown_found = False
    invalid_found = False
    
    # We only sum debits/credits for valid in-window postings to KNOWN accounts
    total_debits = 0
    total_credits = 0

    postings_dir = Path(args.postings)
    if not postings_dir.is_dir():
        sys.exit(2)

    for csv_file in sorted(postings_dir.glob("*.csv")):
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header_skipped = False
                for row in reader:
                    # Ignore blank lines
                    if not row or all(col.strip(" \t\r\n") == "" for col in row):
                        continue
                    if not header_skipped:
                        header_skipped = True
                        continue
                        
                    parsed = parse_journal_line(row)
                    if not parsed:
                        continue
                    
                    p_date = parsed["posting_date"]
                    acct = parsed["account_id"]
                    deb = parsed["debit_cents"]
                    crd = parsed["credit_cents"]
                    
                    if p_date == "posting_date" or not p_date:
                        continue
                        
                    if not in_window(p_date, start_date, end_date):
                        continue
                    
                    # Validate debits and credits formats (non-negative integer)
                    if not is_non_negative_integer(deb) or not is_non_negative_integer(crd):
                        invalid_found = True
                        continue
                        
                    d_val = int(deb)
                    c_val = int(crd)
                    
                    # Both-zero or both-nonzero validation
                    if d_val == 0 and c_val == 0:
                        invalid_found = True
                        continue
                    if d_val != 0 and c_val != 0:
                        invalid_found = True
                        continue
                        
                    # Look up account case-insensitively
                    folded = normalize_account(acct)
                    if folded not in chart:
                        unknown_found = True
                        continue
                        
                    canon = chart[folded]["canonical"]
                    debit_sums[canon] = debit_sums.get(canon, 0) + d_val
                    credit_sums[canon] = credit_sums.get(canon, 0) + c_val
                    
                    total_debits += d_val
                    total_credits += c_val
        except Exception:
            sys.exit(2)

    # Compute snapshot rows
    report_rows = []
    all_accounts = set(debit_sums.keys()) | set(credit_sums.keys())
    
    for canon in all_accounts:
        debits = debit_sums.get(canon, 0)
        credits = credit_sums.get(canon, 0)
        
        # normal_balance is fetched from the chart mapping
        folded = canon.lower()
        normal = chart[folded]["normal_balance"]
        
        # Netting calculation:
        # debit-normal uses: sum(debit) - sum(credit)
        # credit-normal uses: sum(credit) - sum(debit)
        if normal == "debit":
            net = debits - credits
        else:
            net = credits - debits
            
        if net == 0:
            continue
            
        magnitude = abs(net)
        
        # Side markers:
        # debit-normal: non-negative -> DR, negative -> CR
        # credit-normal: non-negative -> CR, negative -> DR
        if normal == "debit":
            side = "DR" if net >= 0 else "CR"
        else:
            side = "CR" if net >= 0 else "DR"
            
        report_rows.append((canon, magnitude, side))

    # Sort case-insensitively by account ID ascending
    report_rows.sort(key=lambda x: x[0].lower())
    
    with open(args.snapshot, "w", encoding="utf-8") as f:
        for r in report_rows:
            f.write(f"{r[0]};{r[1]};{r[2]}\n")
            
    # Exit codes
    if unknown_found or invalid_found or total_debits != total_credits:
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
