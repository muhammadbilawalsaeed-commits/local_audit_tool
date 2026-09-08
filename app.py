"""
Local Business Audit Tool (Phase 3 - English UI)
------------------------------------------------------------
Same functionality as before, all user-facing text in English
for a global audience.
"""

import re
import time
import requests
import pandas as pd
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Local Business Audit Tool", layout="wide")

PLACES_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"
PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

EMAIL_REGEX_SIMPLE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


# ------------------------- Supabase setup -------------------------

@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        return None
    if not url or not key:
        return None
    return create_client(url, key)


supabase: Client = init_supabase()

if "user" not in st.session_state:
    st.session_state.user = None
if "session" not in st.session_state:
    st.session_state.session = None


def show_auth_ui():
    st.title("🏪 Local Business Audit Tool")
    st.caption("Please log in or create an account to continue.")

    tab_login, tab_signup = st.tabs(["🔑 Log In", "🆕 Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In", type="primary")
            if submitted:
                if not EMAIL_REGEX_SIMPLE.match(email):
                    st.error("Please enter a valid email address.")
                else:
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state.user = res.user
                        st.session_state.session = res.session
                        st.rerun()
                    except Exception:
                        st.error("Login failed. Check your email/password, or sign up first.")

    with tab_signup:
        with st.form("signup_form"):
            email2 = st.text_input("Email", key="signup_email")
            password2 = st.text_input("Password (at least 6 characters)", type="password", key="signup_password")
            submitted2 = st.form_submit_button("Sign Up", type="primary")
            if submitted2:
                if not EMAIL_REGEX_SIMPLE.match(email2):
                    st.error("Please enter a valid email address.")
                elif len(password2) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    try:
                        supabase.auth.sign_up({"email": email2, "password": password2})
                        st.success("Account created! Check your email for a confirmation link, then log in.")
                    except Exception as e:
                        st.error(f"Sign up failed: {e}")


# ------------------------- Audit tool logic -------------------------

def text_search(query, api_key, max_pages=1):
    results = []
    params = {"query": query, "key": api_key}
    for _ in range(max_pages):
        resp = requests.get(PLACES_TEXT_SEARCH, params=params, timeout=15).json()
        if resp.get("status") not in ("OK", "ZERO_RESULTS"):
            st.warning(f"API status: {resp.get('status')} - {resp.get('error_message', '')}")
            break
        results.extend(resp.get("results", []))
        next_token = resp.get("next_page_token")
        if not next_token:
            break
        time.sleep(2)
        params = {"pagetoken": next_token, "key": api_key}
    return results


def get_place_details(place_id, api_key):
    fields = "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,opening_hours,business_status,url"
    params = {"place_id": place_id, "fields": fields, "key": api_key}
    resp = requests.get(PLACES_DETAILS, params=params, timeout=15).json()
    return resp.get("result", {})


def get_pagespeed_scores(url, api_key=None):
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
    score = 0
    max_score = 0
    max_score += 30
    if details.get("website"):
        score += 8
    if details.get("formatted_phone_number"):
        score += 7
    if details.get("opening_hours"):
        score += 7
    if details.get("rating", 0) and details.get("rating", 0) >= 4.0:
        score += 8
    for key in ["performance", "seo", "accessibility", "best_practices"]:
        max_score += 10
        val = pagespeed.get(key)
        if val is not None:
            score += (val / 100) * 10
    for key in ["https", "title_tag", "meta_description", "mobile_viewport"]:
        max_score += 7.5
        if onpage.get(key):
            score += 7.5
    if max_score == 0:
        return 0
    return round((score / max_score) * 100)


def show_audit_tool():
    with st.sidebar:
        st.success(f"✅ Logged in as **{st.session_state.user.email}**")
        if st.button("Log Out"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.session_state.session = None
            st.rerun()
        st.divider()
        st.header("Settings")
        places_api_key = st.text_input("Google Places API Key", type="password")
        pagespeed_api_key = st.text_input("PageSpeed API Key (optional)", type="password")

    st.title("🏪 Local Business Audit Tool")
    st.caption("Google Places + PageSpeed Insights (official APIs) — Local SEO Health Score.")

    query = st.text_input("Business name + location", placeholder="e.g. Starbucks, New York")
    run = st.button("🔍 Run Audit", type="primary")

    if run:
        if not places_api_key:
            st.error("Please enter your Google Places API key in the sidebar.")
        elif not query:
            st.error("Please enter a business name and location.")
        else:
            with st.spinner("Searching for the business..."):
                results = text_search(query, places_api_key)

            if not results:
                st.warning("No results found. Try a different name or location.")
            else:
                options = {f"{r['name']} — {r.get('formatted_address', '')}": r["place_id"] for r in results[:5]}
                chosen_label = st.selectbox("Select the correct business:", list(options.keys()))
                place_id = options[chosen_label]

                with st.spinner("Running full audit..."):
                    details = get_place_details(place_id, places_api_key)
                    website = details.get("website", "")
                    pagespeed = get_pagespeed_scores(website, pagespeed_api_key) if website else {}
                    onpage = check_onpage_basics(website) if website else {}
                    health_score = compute_health_score(details, pagespeed, onpage)

                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric("Local SEO Health Score", f"{health_score}/100")
                with col2:
                    st.write(f"**{details.get('name', '')}**")
                    st.write(details.get("formatted_address", ""))
                    st.write(f"⭐ {details.get('rating', 'N/A')} ({details.get('user_ratings_total', 0)} reviews)")

                st.divider()
                st.subheader("📍 Google Business Profile")
                gbp_rows = [
                    ("Website listed", "✅" if details.get("website") else "❌"),
                    ("Phone number listed", "✅" if details.get("formatted_phone_number") else "❌"),
                    ("Opening hours set", "✅" if details.get("opening_hours") else "❌"),
                    ("Rating ≥ 4.0", "✅" if details.get("rating", 0) >= 4.0 else "❌"),
                ]
                st.table(pd.DataFrame(gbp_rows, columns=["Check", "Status"]))

                if website:
                    st.subheader("🌐 Website Technical Health")
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
                    st.warning("This business's website is not listed on Google — that's a great opportunity to pitch them!")

                st.divider()
                report_data = {
                    "Business Name": [details.get("name", "")],
                    "Address": [details.get("formatted_address", "")],
                    "Phone": [details.get("formatted_phone_number", "")],
                    "Website": [website],
                    "Rating": [details.get("rating", "")],
                    "Reviews": [details.get("user_ratings_total", "")],
                    "Health Score": [health_score],
                }
                df_report = pd.DataFrame(report_data)
                csv = df_report.to_csv(index=False).encode("utf-8-sig")
                st.download_button("⬇️ Download Audit Report (CSV)", data=csv,
                                    file_name=f"audit_{details.get('name', 'business').replace(' ', '_')}.csv",
                                    mime="text/csv")


# ------------------------- Main -------------------------

if supabase is None:
    st.error(
        "⚠️ Supabase is not configured. Please add SUPABASE_URL and SUPABASE_KEY "
        "to your secrets (see README)."
    )
    st.stop()

if st.session_state.user is None:
    show_auth_ui()
else:
    show_audit_tool()
