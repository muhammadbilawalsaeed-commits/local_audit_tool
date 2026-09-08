# Local Business Audit Tool — Poori Guide (Step by Step)

## Yeh tool kya karta hai
Kisi bhi business ka naam dein, ye:
1. Google Business Profile check karta hai (website, phone, hours, rating)
2. Website ki technical health check karta hai (speed, SEO, mobile-friendliness) — Google ki apni FREE PageSpeed API se
3. Sab mila kar ek **Health Score (0-100)** deta hai
4. CSV report export karta hai

**Use case:** Low-score businesses ko dhoondein aur unhe apni SEO/website service pitch karein — ye khud ek client-acquisition machine ban jata hai.

---

## STEP 1: Apne computer par tool chalana (testing ke liye)

1. Python install karein (agar nahi hai): https://www.python.org/downloads/ (3.9 ya usse naya version)
2. Yeh 3 files jo maine di hain, ek folder mein rakhein: `app.py`, `requirements.txt`, `README.md`
3. Terminal/Command Prompt kholein, us folder mein jayein:
   ```
   cd path/to/local_audit_tool
   ```
4. Libraries install karein:
   ```
   pip install -r requirements.txt
   ```
5. Tool run karein:
   ```
   streamlit run app.py
   ```
6. Browser mein automatically khul jayega (`http://localhost:8501`)

Yahan tak koi coding nahi karni padi — bas terminal mein 2 commands chalayi hain.

---

## STEP 2: API Keys lena (zaroori)

### Google Places API Key (paid, lekin $200/month free credit milta hai naye accounts ko)
1. https://console.cloud.google.com/ par jayein → naya project banayein
2. "APIs & Services" → "Library" → "Places API" search karke Enable karein
3. "Credentials" → "Create Credentials" → "API Key" — yehi key sidebar mein daalni hai
4. (Recommended) key ko "Places API" tak restrict kar dein security ke liye

### PageSpeed Insights API Key (bilkul FREE)
1. Usi Google Cloud project mein "PageSpeed Insights API" search karke Enable karein
2. Wahi ya nayi API key bana lein — koi billing zaroori nahi

---

## STEP 3: Test karein
Sidebar mein dono keys daalein, kisi bhi business ka naam + location likhein (jaise "Al-Fateh Bakers, Lahore"), "Run Audit" dabayein. Result aana chahiye.

Agar koi error aaye, mujhe error ka screenshot bhej dein — main fix kar dunga.

---

## STEP 4: Internet par live karna (deploy karna) — VS Code KI ZAROORAT NAHI

Jab local testing sahi lage, tool ko live website banane ke liye **Streamlit Community Cloud** sabse asaan hai (FREE):

1. https://github.com par free account banayein (agar nahi hai)
2. Yeh 3 files ek naye GitHub repository mein upload karein (GitHub website par seedha "Add file" → "Upload files" se — koi command line ya VS Code nahi chahiye)
3. https://share.streamlit.io par jayein, GitHub se login karein
4. "New app" → apni repository choose karein → `app.py` select karein → Deploy dabayein
5. 2-3 minute mein aapka tool live ho jayega, ek public URL milega jo aap kisi ko bhi bhej sakte hain

Iske baad API keys ko safe rakhne ke liye Streamlit Cloud ke "Secrets" section mein dalna hoga (main aapko exact steps dunga jab aap yahan tak pahunch jayein).

---

## Agla Phase (jab MVP test ho jaye)
1. **Bulk mode**: ek CSV upload karke 50 businesses ka audit ek saath (yeh pichle Lead Generation tool se connect hoga)
2. **Login/Signup + Subscription**: taake aap ise SaaS ki tarah bech sakein
3. **Auto-email**: low-score businesses ko automatically outreach email bhejna

Batayein jab Step 1-3 test ho jayen, phir hum Step 4 (deployment) aur agla phase shuru karte hain.
