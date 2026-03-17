"""
4K Projects — Company Qualifier
Reads unqualified companies from Google Sheets, scrapes their websites,
uses OpenAI to decide if they're a workplace design / office fit-out company,
then writes results back to the sheet.
"""

import os
import json
import time
import sys
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# ── Config ────────────────────────────────────────────────────────────────────
SPREADSHEET_ID    = os.environ["SPREADSHEET_ID"]
SHEET_NAME        = "Companies"
OPENAI_API_KEY    = os.environ["OPENAI_API_KEY"]
GOOGLE_CREDS_JSON = os.environ["GOOGLE_CREDENTIALS"]

# Column indices (0-based)
COL_COMPANY  = 0   # A
COL_WEBSITE  = 1   # B
COL_LOCATION = 2   # C
COL_NOTES    = 3   # D
COL_RESULT   = 4   # E
COL_REASON   = 5   # F
COL_DATE     = 6   # G

# ── Google Sheets client ──────────────────────────────────────────────────────
def get_sheet():
    try:
        creds_dict = json.loads(GOOGLE_CREDS_JSON)
    except json.JSONDecodeError as e:
        print(f"❌ GOOGLE_CREDENTIALS secret is not valid JSON: {e}")
        print("   Make sure you copied the entire JSON file content into the secret.")
        sys.exit(1)

    service_email = creds_dict.get("client_email", "unknown")
    print(f"   Service account: {service_email}")
    print(f"   Spreadsheet ID:  {SPREADSHEET_ID}")

    try:
        # Use only the Sheets API scope (no Drive needed)
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        print(f"   ✅ Connected to sheet: {SHEET_NAME}")
        return sheet
    except gspread.exceptions.APIError as e:
        print(f"❌ Google Sheets API error: {e}")
        print(f"   → Make sure the Sheets API is enabled in your Google Cloud project.")
        print(f"   → Visit: https://console.cloud.google.com/apis/library/sheets.googleapis.com")
        sys.exit(1)
    except PermissionError:
        print(f"❌ Permission denied accessing the spreadsheet.")
        print(f"   → Share the sheet with: {service_email}")
        print(f"   → Give it 'Editor' access.")
        print(f"   → Sheet URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error connecting to sheet: {type(e).__name__}: {e}")
        sys.exit(1)

# ── Web scraping ──────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def scrape_website(url: str) -> str:
    """Return up to 2000 chars of visible text from the homepage."""
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:2000]
    except Exception as e:
        return f"[scrape error: {e}]"

# ── AI qualification ──────────────────────────────────────────────────────────
TARGET_PROFILE = """
4K Projects is a 3D visualisation studio that creates CGI images for companies
that design and deliver office/workplace interior projects. Their ideal clients are:
- Interior design studios specialising in offices or workplaces
- Office fit-out contractors
- Workplace design consultancies
- Architecture firms with a strong commercial/workplace interiors focus
- Space planning and workplace strategy companies

NOT a good fit:
- Residential interior designers
- Retail fit-out companies (unless they also do commercial offices)
- Tech/software companies
- Manufacturers or suppliers (furniture, flooring, etc.) — unless they also do design/install
- Estate agents / property companies
- Anything unrelated to physical workplace design or fit-out
"""

def qualify_company(company: str, website: str, website_text: str) -> tuple[str, str]:
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""
You are a business development assistant for 4K Projects, a 3D visualisation studio.

TARGET CLIENT PROFILE:
{TARGET_PROFILE}

Analyse this company and decide whether they fit our target profile.

Company name: {company}
Website URL: {website}
Website content (first 2000 chars):
\"\"\"
{website_text}
\"\"\"

Respond in JSON with exactly these two fields:
{{
  "result": "✅ Qualified" | "❌ Not a Fit" | "⚠️ Needs Review",
  "reason": "One sentence explanation (max 20 words)"
}}

Use "⚠️ Needs Review" only when there is genuine ambiguity.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("result", "⚠️ Needs Review"), data.get("reason", "Unable to determine")
    except Exception as e:
        return "⚠️ Needs Review", f"AI error: {e}"

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("🔌 Connecting to Google Sheets…")
    sheet = get_sheet()
    rows  = sheet.get_all_values()

    if not rows:
        print("Sheet is empty.")
        return

    data  = rows[1:]  # skip header
    today = time.strftime("%d/%m/%Y")

    processed = 0
    for i, row in enumerate(data, start=2):
        while len(row) < 7:
            row.append("")

        company = row[COL_COMPANY].strip()
        website = row[COL_WEBSITE].strip()
        result  = row[COL_RESULT].strip()

        if not company:
            continue
        if result in ("✅ Qualified", "❌ Not a Fit", "⚠️ Needs Review"):
            print(f"  ↷ Skipping {company} (already qualified)")
            continue

        print(f"\n🔍 Processing: {company} ({website})")

        text = scrape_website(website)
        print(f"   Scraped {len(text)} chars")

        qual_result, qual_reason = qualify_company(company, website, text)
        print(f"   → {qual_result}: {qual_reason}")

        sheet.update(f"E{i}:G{i}", [[qual_result, qual_reason, today]])
        processed += 1
        time.sleep(1)

    print(f"\n✅ Done — processed {processed} companies.")

if __name__ == "__main__":
    main()
