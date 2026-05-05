import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open("ANNUAL-BUDGET 2026 (MAR - Present)")
worksheet = sheet.sheet1

print("Connected to:", sheet.title)
print("First worksheet:", worksheet.title)