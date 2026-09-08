"""
Local Business Audit Tool (Phase 1 - MVP)
-------------------------------------------
Goal: Give any business a "Local SEO Health Score" like Semrush's Local
Dashboard does — using OFFICIAL, legal Google APIs (no scraping).

What it checks:
  1. Google Business Profile presence (via Places API): rating, review
     count, whether phone/website/hours are filled in.
  2. Website technical health (via Google PageSpeed Insights API - FREE):
     Performance, SEO, Accessibility, Best Practices scores.
  3. Basic on-page checks (title tag, meta description, mobile viewport,
     HTTPS) by fetching the business's own public homepage.

Output: an overall Health Score (0-100) + a breakdown + CSV/report export.

Run locally:
  pip install -r requirements.txt
  streamlit run app.py
"""

import re
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Local Business Audit Tool", layout="wide")

PLACES_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"
PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def find_business(query, api_key):
    params = {"query": query, "key": api_key}
    resp = requests.get(PLACES_TEXT_SEARCH, params=params, timeout=15).json()
    return resp.get("results", [])


def get_place_details(place_id, api_key):
    fields = "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,opening_hours,business_status,url,photos"
    params = {"place_id": place_id, "fields": fields, "key": api_key}
    resp = requests.get(PLACES_DETAILS, params=params, timeout=15).json()
    return resp.get("result", {})


def get_pagespeed_scores(url, api_key=None):
    """FREE Google API - no billing needed, just a key (or works keyless with low quota)."""
    scores = {"performance": None, "seo": None, "accessibility": None, "best_practices": None}
    if not url:
        return scores
    try:
        params = {"url": url, "category": ["PERFORMANCE", "SEO", "ACCESSIBILITY", "BEST_PRACTICES"]}
        if api_key:
            params["key"] = api_key
        resp = requests.get(PAGESPEED_API, params=params, timeout=30).json()
        cats = resp.get("lighthouseResult", {}).get("categories", {})
        scores["performance"] = round(cats.get("performance", {}).get("score", 0) * 100) if cats.get("performance") else None
        scores["seo"] = round(cats.get("seo", {}).get("score", 0) * 100) if cats.get("seo") else None
        scores["accessibility"] = round(cats.get("accessibility", {}).get("score", 0) * 100) if cats.get("accessibility") else None
        scores["best_practices"] = round(cats.get("best-practices", {}).get("score", 0) * 100) if cats.get("best-practices") else None
    except Exception:
        pass
    return scores


def check_onpage_basics(url, timeout=8):
    """Fetch the business's own public homepage and check basic SEO hygiene."""
    checks = {"https": False, "title_tag": False, "meta_description": False, "mobile_viewport": False}
    if not url:
        return checks
    try:
        checks["https"] = url.startswith("https://")
        headers = {"User-Agent": "Mozilla/5.0 (LocalAuditTool)"}
        r = requests.get(url, headers=headers, timeout=timeout)
        html = r.text
        checks["title_tag"] = bool(re.search(r"<title>.{5,}</title>", html, re.IGNORECASE))
        checks["meta_description"] = bool(re.search(r'name=["\']description["\']', html, re.IGNORECASE))
        checks["mobile_viewport"] = bool(re.search(r'name=["\']viewport["\']', html, re.IGNORECASE))
    except Exception:
        pass
    return checks


def compute_health_score(details, pagespeed, onpage):
    """Simple weighted score out of 100 - transparent, easy to explain to a client."""
    score = 0
    max_score = 0

    # Google Business Profile completeness (30 pts)
    max_score += 30
    if details.get("website"):
        score += 8
    if details.get("formatted_phone_number"):
        score += 7
    if details.get("opening_hours"):
        score += 7
    if details.get("rating", 0) and details.get("rating", 0) >= 4.0:
        score += 8

    # PageSpeed scores (40 pts total, 10 each)
    for key in ["performance", "seo", "accessibility", "best_practices"]:
        max_score += 10
        val = pagespeed.get(key)
        if val is not None:
            score += (val / 100) * 10

    # On-page basics (30 pts, ~7.5 each)
    for key in ["https", "title_tag", "meta_description", "mobile_viewport"]:
        max_score += 7.5
        if onpage.get(key):
            score += 7.5

    if max_score == 0:
        return 0
    return round((score / max_score) * 100)


# ------------------------- UI -------------------------

st.title("🏪 Local Business Audit Tool — MVP")
st.caption("Google Places + PageSpeed Insights (official APIs) — Local SEO Health Score, jaisa Semrush Local Dashboard.")

with st.sidebar:
    st.header("Settings")
    places_api_key = st.text_input("Google Places API Key", type="password")
    pagespeed_api_key = st.text_input("PageSpeed API Key (optional, boosts quota)", type="password")
    st.caption("Places API paid hai (free credit milta hai). PageSpeed API bilkul FREE hai.")

query = st.text_input("Business name + location", placeholder="e.g. Al-Fateh Bakers, Lahore")
run = st.button("🔍 Run Audit", type="primary")

if run:
    if not places_api_key:
        st.error("Sidebar mein Google Places API key daalein.")
    elif not query:
        st.error("Business name aur location likhein.")
    else:
        with st.spinner("Business dhoondi ja rahi hai..."):
            results = find_business(query, places_api_key)

        if not results:
            st.warning("Business nahi mili. Naam/location check karke dobara try karein.")
        else:
            # Let user pick if multiple matches
            options = {f"{r['name']} — {r.get('formatted_address', '')}": r["place_id"] for r in results[:5]}
            chosen_label = st.selectbox("Sahi business chunain:", list(options.keys()))
            place_id = options[chosen_label]

            with st.spinner("Poora audit chal raha hai (Places + PageSpeed + on-page)..."):
                details = get_place_details(place_id, places_api_key)
                website = details.get("website", "")
                pagespeed = get_pagespeed_scores(website, pagespeed_api_key) if website else {}
                onpage = check_onpage_basics(website) if website else {}
                health_score = compute_health_score(details, pagespeed, onpage)

            # --- Score header ---
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                st.metric("Local SEO Health Score", f"{health_score}/100")
            with col2:
                st.write(f"**{details.get('name', '')}**")
                st.write(details.get("formatted_address", ""))
                st.write(f"⭐ {details.get('rating', 'N/A')} ({details.get('user_ratings_total', 0)} reviews)")

            st.divider()

            # --- Google Business Profile checks ---
            st.subheader("📍 Google Business Profile")
            gbp_rows = [
                ("Website listed", "✅" if details.get("website") else "❌"),
                ("Phone number listed", "✅" if details.get("formatted_phone_number") else "❌"),
                ("Opening hours set", "✅" if details.get("opening_hours") else "❌"),
                ("Rating ≥ 4.0", "✅" if details.get("rating", 0) >= 4.0 else "❌"),
            ]
            st.table(pd.DataFrame(gbp_rows, columns=["Check", "Status"]))

            # --- Website health ---
            if website:
                st.subheader("🌐 Website Technical Health (PageSpeed Insights)")
                ps_cols = st.columns(4)
                labels = {"performance": "Performance", "seo": "SEO", "accessibility": "Accessibility", "best_practices": "Best Practices"}
                for i, key in enumerate(["performance", "seo", "accessibility", "best_practices"]):
                    val = pagespeed.get(key)
                    ps_cols[i].metric(labels[key], f"{val}/100" if val is not None else "N/A")

                st.subheader("🔎 On-Page Basics")
                onpage_rows = [
                    ("HTTPS (secure)", "✅" if onpage.get("https") else "❌"),
                    ("Title tag present", "✅" if onpage.get("title_tag") else "❌"),
                    ("Meta description present", "✅" if onpage.get("meta_description") else "❌"),
                    ("Mobile-friendly viewport tag", "✅" if onpage.get("mobile_viewport") else "❌"),
                ]
                st.table(pd.DataFrame(onpage_rows, columns=["Check", "Status"]))
            else:
                st.warning("Is business ki website Google par listed nahi hai — yeh sabse bada opportunity hai unhe pitch karne ke liye!")

            # --- Export ---
            st.divider()
            report_data = {
                "Business Name": [details.get("name", "")],
                "Address": [details.get("formatted_address", "")],
                "Phone": [details.get("formatted_phone_number", "")],
                "Website": [website],
                "Rating": [details.get("rating", "")],
                "Reviews": [details.get("user_ratings_total", "")],
                "Health Score": [health_score],
                "Performance": [pagespeed.get("performance")],
                "SEO": [pagespeed.get("seo")],
                "Accessibility": [pagespeed.get("accessibility")],
                "Best Practices": [pagespeed.get("best_practices")],
                "HTTPS": [onpage.get("https")],
                "Title Tag": [onpage.get("title_tag")],
                "Meta Description": [onpage.get("meta_description")],
                "Mobile Viewport": [onpage.get("mobile_viewport")],
            }
            df_report = pd.DataFrame(report_data)
            csv = df_report.to_csv(index=False).encode("utf-8-sig")
            st.download_button("⬇️ Download Audit Report (CSV)", data=csv,
                                file_name=f"audit_{details.get('name', 'business').replace(' ', '_')}.csv",
                                mime="text/csv")

st.divider()
st.caption(
    "Pitch idea: Yeh score kam hone wale businesses ko dikhayein (\"Aapka score sirf 42/100 hai, "
    "main aapko 80+ tak le ja sakta hoon\") aur unhe SEO/website fixing service bechein — "
    "isi tool se apna client-acquisition automate karein."
)
