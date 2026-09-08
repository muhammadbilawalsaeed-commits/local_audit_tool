# Local Business Audit Tool — Phase 3 (Signup/Login)

## Kya naya hai
Ab tool ke istemal se pehle **login/signup zaroori hai** (real user accounts, Supabase se). Ye Phase 4 (Stripe subscription) ki buniyad hai.

---

## STEP 1: Apni Supabase details `secrets.toml` mein daalein

1. `.streamlit` folder ke andar jo `secrets.toml` file hai, usay text editor (Notepad) mein kholein.
2. `SUPABASE_URL` aur `SUPABASE_KEY` ki jagah apni **Project URL** aur **Publishable key** paste karein (jo aapne Supabase se copy ki thi).
3. Save karein.

**Zaroori:** Ye file apni real values ke saath GitHub par kabhi upload NA karein — humne `.gitignore` file bana di hai jo isay automatically skip kar degi.

---

## STEP 2: Supabase mein Email Auth confirm karein

1. Supabase dashboard mein apne project mein jayein.
2. Left menu → "Authentication" → "Providers" (ya "Sign In / Providers").
3. "Email" provider already ON hona chahiye (default hota hai) — confirm kar lein.
4. **Testing ke liye asaan banane ke liye:** "Authentication" → "Sign In / Up" (ya "Email" settings) mein "Confirm email" ka toggle **OFF** kar dein. Isse naye accounts turant use ho sakenge, email confirm kiye bagair (baad mein production mein ise wapas ON kar sakte hain).

---

## STEP 3: Local test karein

1. Terminal mein us folder mein jayein:
   ```
   cd Desktop\local_audit_tool_v2
   ```
2. Nayi library install karein:
   ```
   python -m pip install -r requirements.txt
   ```
3. Tool chalayein:
   ```
   python -m streamlit run app.py
   ```
4. Browser mein "Sign Up" tab se ek test account banayein (apna email + password), phir "Login" tab se login karein.
5. Login hone ke baad wahi audit tool dikhega jaisa pehle tha, sath mein sidebar mein "Logout" button aur aapka email.

---

## STEP 4: GitHub + Streamlit Cloud par update karein

1. GitHub repository mein jayein jo aapne pehle banayi thi.
2. `app.py` aur `requirements.txt` files ko **overwrite** karein (naya content upload karein — GitHub "Upload files" se dobara upload karne par purani file replace ho jati hai).
3. **Secrets ko Streamlit Cloud mein alag se dalna hoga** (GitHub par nahi):
   - https://share.streamlit.io par apni app kholein
   - "Settings" (3-dot menu) → "Secrets"
   - Yahan likhein:
     ```
     SUPABASE_URL = "https://YOUR-PROJECT-REF.supabase.co"
     SUPABASE_KEY = "sb_publishable_xxxxxxxxxxxxxxxxxxxx"
     ```
   - Save karein — app automatically restart ho jayegi.

---

## Agla Phase
Jab Signup/Login test ho jaye (account banayein, login/logout try karein), batayein — phir hum **Phase 4: Free Trial + Stripe Subscription** shuru karenge, taake ye asal SaaS bane jisse earning ho sake.
