"""
4K Projects — Company Qualifier
Reads unqualified companies from Google Sheets, scrapes their websites,
uses OpenAI to decide if they're a workplace design / office fit-out company,
then writes results back to the sheet.
"""

import os
import json
import time
import re
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# ── Config ────────────────────────────────────────────────────────────────────
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SHEET_NAME      = "Companies"
OPENAI_API_KEY  = os.environ["OPENAI_API_KEY"]

# Google credentials come in as a JSON string stored in a secret
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
    creds_dict = json.loads(GOOGLE_CREDS_JSON)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

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
        # Remove scripts/styles
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
    """
    Returns (result, reason).
    result is one of: "✅ Qualified", "❌ Not a Fit", "⚠️ Needs Review"
    """
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
        result = data.get("result", "⚠️ Needs Review")
        reason = data.get("reason", "Unable to determine")
        return result, reason
    except Exception as e:
        return "⚠️ Needs Review", f"AI error: {e}"

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("🔌 Connecting to Google Sheets…")
    sheet = get_sheet()
    rows = sheet.get_all_values()

    if not rows:
        print("Sheet is empty.")
        return

    header = rows[0]
    data   = rows[1:]
    today  = time.strftime("%d/%m/%Y")

    processed = 0
    for i, row in enumerate(data, start=2):  # 1-indexed; row 1 is header
        # Pad row if needed
        while len(row) < 7:
            row.append("")

        company = row[COL_COMPANY].strip()
        website = row[COL_WEBSITE].strip()
        result  = row[COL_RESULT].strip()

        # Skip already qualified rows or rows without a company name
        if not company:
            continue
        if result in ("✅ Qualified", "❌ Not a Fit", "⚠️ Needs Review"):
            print(f"  ↷ Skipping {company} (already qualified)")
            continue

        print(f"\n🔍 Processing: {company} ({website})")

        # Scrape
        text = scrape_website(website)
        print(f"   Scraped {len(text)} chars")

        # Qualify
        qual_result, qual_reason = qualify_company(company, website, text)
        print(f"   → {qual_result}: {qual_reason}")

        # Write back
        sheet.update(
            f"E{i}:G{i}",
            [[qual_result, qual_reason, today]]
        )
        processed += 1
        time.sleep(1)  # be polite to rate limits

    print(f"\n✅ Done — processed {processed} companies.")

if __name__ == "__main__":
    main()
