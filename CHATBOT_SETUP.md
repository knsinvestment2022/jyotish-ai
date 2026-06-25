# Jyotish AI — Chatbot Setup Guide

Complete instructions to go from zero to a live astrology chatbot website.

---

## What Was Built

| File | What It Does |
|---|---|
| `rag_pipeline.py` | One-time script — reads all 21 PDFs and builds the knowledge index |
| `rag_engine.py` | Finds relevant book passages for each user question |
| `chat_engine.py` | Calls Claude API with book context + expert system prompt |
| `models.py` | Database: users, sessions, messages, feedback |
| `app.py` | Flask app with all routes (updated) |
| `templates/landing.html` | Public homepage with signup |
| `templates/signup.html` | Account creation |
| `templates/login.html` | Sign in |
| `templates/chat.html` | Main chat interface |
| `templates/admin_feedback.html` | Your feedback dashboard |
| `templates/admin_users.html` | Your users dashboard |

---

## Step 1 — Install Dependencies

Open a terminal in the `astro_site/` folder and run:

```bash
pip install flask flask-sqlalchemy flask-login werkzeug stripe pyswisseph \
            timezonefinder pytz requests reportlab gunicorn \
            anthropic chromadb sentence-transformers pypdf
```

> **Note:** `sentence-transformers` and `chromadb` download a ~100MB AI model the first time. This is a one-time download.

---

## Step 2 — Get Your Anthropic API Key

1. Go to https://console.anthropic.com
2. Sign up / log in
3. Click **API Keys** → **Create Key**
4. Copy your key (starts with `sk-ant-...`)
5. Set a spending limit (recommend $20/month to start)

---

## Step 3 — Create a `.env` File

Create `astro_site/.env` with these values:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
SECRET_KEY=any-random-long-string-here
STRIPE_SECRET_KEY=sk_test_your-stripe-key
STRIPE_PUBLISHABLE_KEY=pk_test_your-stripe-key
BASE_URL=http://localhost:5000
ADMIN_EMAIL=knsinvestment2022@gmail.com
FREE_MESSAGE_LIMIT=20
BETA_USER_LIMIT=100
```

> **Secret key:** generate one with `python -c "import secrets; print(secrets.token_hex(32))"`

---

## Step 4 — Build the Knowledge Index (Run Once)

This reads all 21 PDF books and creates the ChromaDB search index:

```bash
cd astro_site
python rag_pipeline.py
```

This takes **5–15 minutes** depending on your computer. It creates a `chroma_db/` folder.

You only need to run this once. Run again if you add new books.

---

## Step 5 — Run Locally

```bash
cd astro_site
python app.py
```

Open http://localhost:5000 — you should see the landing page.

Test it:
1. Click **Get Free Access** → sign up
2. Click **Birth Details** → enter your birth info
3. Ask: "What does my Venus Mahadasha mean?"

---

## Step 6 — Deploy to Render.com (Live on the Internet)

### 6a. Push your code to GitHub
```bash
git init
git add .
git commit -m "Jyotish AI chatbot"
# Create a repo at github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/jyotish-ai.git
git push -u origin main
```

### 6b. Create the app on Render
1. Go to https://render.com → **New Web Service**
2. Connect your GitHub repo
3. Settings:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Add all your environment variables from `.env`
5. Click **Deploy**

### 6c. Run the RAG pipeline on Render (one-time)
In Render dashboard → **Shell** tab:
```bash
python rag_pipeline.py
```

### 6d. Add a custom domain (optional)
In Render → Settings → Custom Domain → add your domain (e.g., `jyotishai.com`)

---

## Step 7 — Get Your First 100 Users

### Reddit (free, high-intent audience)
Post in these communities:
- r/vedicastrology (180K members)
- r/astrology (1.4M members)
- r/hinduism (200K members)
- r/jyotish

**Sample post:**
> "I built an AI trained on 21 classical Vedic astrology texts (B.V. Raman, K.S. Charak, KP system etc). First 100 beta users get free unlimited access in exchange for feedback. Ask anything — career, marriage, immigration, stocks. DM me or sign up at [your-link]"

### Facebook Groups
Search for: "Vedic Astrology", "Jyotish", "Hindu Astrology"
Combined membership: 500K+ people

### WhatsApp / Telegram
Share in any astrology groups you're in.

### Twitter/X
Post a free sample reading (screenshot of a good answer) with your link.

---

## Monitoring Your Users

After people sign up, check:
- http://your-site.com/admin/users — see all users
- http://your-site.com/admin/feedback — see all ratings and comments

Both pages are protected — only your email (`knsinvestment2022@gmail.com`) can access them.

---

## Pricing Model (After Beta)

After first 100 users, set in `.env`:
```
FREE_MESSAGE_LIMIT=5
```
Free users get 5 messages then see an upgrade prompt.

Add a Pro subscription ($9.99/month) in Stripe → create a Subscription product → add a `/upgrade` page.

---

## Costs Estimate

| Service | Free Tier | Paid |
|---|---|---|
| Render.com | Free (sleeps after 15min) | $7/month (always-on) |
| Claude API (Haiku) | Pay per use | ~$0.001 per message |
| ChromaDB | Free (local) | Free |
| Stripe | Free | 2.9% + $0.30 per transaction |

**For 100 users × 10 messages = 1,000 messages ≈ $1 in API costs.**

---

## Switching to a Smarter Model

In `chat_engine.py`, change:
```python
MODEL = "claude-haiku-4-5-20251001"   # fast + cheap
# to:
MODEL = "claude-sonnet-4-6"            # smarter, ~10x cost
```

---

## Adding New Books

1. Drop new PDFs into `Vedic_Astrology/`
2. Run `python rag_pipeline.py` again
3. The index rebuilds automatically

---

## File Structure

```
astro_site/
├── app.py                  ← Main Flask app (all routes)
├── chat_engine.py          ← Claude API + RAG integration
├── rag_pipeline.py         ← Run once to index books
├── rag_engine.py           ← Retrieves book passages at query time
├── models.py               ← Database models
├── chart_engine.py         ← Vedic chart calculation
├── location.py             ← Geocoding + timezone
├── reading_generator.py    ← Generates readings
├── pdf_export.py           ← PDF download
├── requirements.txt        ← All dependencies
├── chroma_db/              ← Created by rag_pipeline.py
├── astro.db                ← SQLite database (auto-created)
├── .env                    ← Your secrets (never commit this)
└── templates/
    ├── landing.html        ← Public homepage
    ← signup.html          ← Create account
    ├── login.html          ← Sign in
    ├── chat.html           ← Main chat interface
    ├── admin_feedback.html ← Your feedback dashboard
    ├── admin_users.html    ← Your users list
    ├── index.html          ← Legacy reading form
    ├── preview.html        ← Legacy teaser
    └── reading.html        ← Legacy full reading
```
