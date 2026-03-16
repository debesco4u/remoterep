# 4K Projects — Company Qualifier

A one-click AI tool that qualifies companies for outreach by scraping their website and deciding if they're a workplace design / office fit-out company.

## How it works

1. You add companies to the Google Sheet (columns A–D)
2. You open the dashboard and click **Run Qualifier**
3. A GitHub Action fires — it scrapes each website and uses GPT-4o-mini to classify each company
4. Results are written back to the Google Sheet (Qualified / Not a Fit / Needs Review)

---

## Setup (one-time)

### 1. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

Add these three secrets:

| Secret name | Value |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key (from platform.openai.com) |
| `SPREADSHEET_ID` | `1vwYq8DmSBbc2BOsAgWBNMFMORtbiYuErufPHxEEOFo4` |
| `GOOGLE_CREDENTIALS` | Your Google Service Account JSON (see below) |

### 2. Create a Google Service Account

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → Enable **Google Sheets API** and **Google Drive API**
3. Go to **IAM & Admin → Service Accounts → Create Service Account**
4. Download the JSON key
5. Paste the entire JSON as the `GOOGLE_CREDENTIALS` secret
6. Share your Google Sheet with the service account email (Editor access)

### 3. Enable GitHub Pages

1. Repo → **Settings → Pages**
2. Source: **Deploy from branch → main → / (root)**
3. Your app will be live at: `https://debesco4u.github.io/remoterep/`

### 4. Create a GitHub Personal Access Token

1. GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. New token → tick **`workflow`** scope
3. Copy the token and paste it into the dashboard when you open it

---

## File structure

```
├── index.html                      ← Dashboard (GitHub Pages)
├── qualify.py                      ← AI qualification script
├── .github/
│   └── workflows/
│       └── qualify.yml             ← GitHub Actions workflow
└── README.md
```
