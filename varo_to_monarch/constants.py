"""Constants and regular expressions."""
import re

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
AMOUNT_DECIMAL_RE = re.compile(r"^-?\d+\.\d{2}$")

SECTION_ORDER = [
    "Payments and Credits",
    "Purchases",
    "Fees",
    "Secured Account Transactions",
]

SECTION_TO_ACCOUNT = {
    "Payments and Credits": "Varo Believe Card",
    "Purchases": "Varo Believe Card",
    "Fees": "Varo Believe Card",
    "Secured Account Transactions": "Varo Secured Account",
}

SECTION_SIGN = {
    "Purchases": -1,  # force negative
    "Fees": -1,  # force negative
    "Payments and Credits": 1,  # force positive
    "Secured Account Transactions": 0,  # trust sign shown
}
