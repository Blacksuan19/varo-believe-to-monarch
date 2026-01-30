"""DataFrame post-processing logic."""

import pandas as pd

from .constants import SECTION_SIGN, SECTION_TO_ACCOUNT


def finalize_monarch(df: pd.DataFrame, include_file_names: bool) -> pd.DataFrame:
    """Post-process valid transactions into Monarch-compatible format."""
    if df.empty:
        return df

    df["Account"] = df["Section"].map(SECTION_TO_ACCOUNT).fillna("Varo Believe Card")

    # Apply sign logic
    sign_rule = df["Section"].map(SECTION_SIGN).fillna(0)

    def apply_sign(amt: float, rule: int) -> float:
        if rule == -1:
            return -abs(amt)  # force negative
        elif rule == 1:
            return abs(amt)  # force positive
        else:  # rule == 0
            return amt  # trust sign from PDF

    df["Amount"] = [
        apply_sign(a, int(r)) for a, r in zip(df["AmountParsed"], sign_rule)
    ]

    df["Merchant Name"] = df["Merchant"]

    cols = [
        "Date",
        "Merchant Name",
        "Account",
        "Amount",
    ]
    if include_file_names:
        cols.append("SourceFile")

    out = df[cols].copy()
    out["Date"] = pd.to_datetime(out["Date"], format="%m/%d/%Y", errors="coerce")
    out = out.dropna(subset=["Date"])

    sort_cols = ["Date", "Merchant Name", "Amount"]
    if "SourceFile" in out.columns:
        sort_cols.insert(1, "SourceFile")

    out = out.sort_values(sort_cols).copy()
    out["Date"] = out["Date"].dt.strftime("%m/%d/%Y")
    return out
