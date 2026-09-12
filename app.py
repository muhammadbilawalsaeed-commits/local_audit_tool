"""
Local Business Audit Tool (Phase 7 - Free Data Source + Polished Design)
---------------------------------------------------------------------------
Key change: business search now uses OpenStreetMap's free Nominatim API
instead of Google Places, so NO billing account is required to run this
tool. Google Places can be added back later as a premium data source once
billing is sorted out — the audit/scoring/email/subscription logic below
does not depend on which search source is used.
"""

import re
import time
from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.text import MIMEText

import requests
import pandas as pd
import streamlit as st
import stripe
from supabase import create_client, Client

st.set_page_config(page_title="Local Business Audit Tool", layout="wide", page_icon="🏪")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
NOMINATIM_HEADERS = {"User-Agent": "LocalBusinessAuditTool/1.0 (contact: owner)"}

EMAIL_REGEX_SIMPLE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
STATUS_OPTIONS = ["sent", "opened", "replied", "no response"]


# ------------------------- Custom design -------------------------

def inject_custom_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.01em; }

        .score-card {
            background: #FFFFFF;
            border: 1px solid #E4E1D8;
            border-radius: 10px;
            padding: 1.5rem;
        }
        .score-number {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 3rem;
            font-weight: 700;
            line-height: 1;
        }
        .score-good { color: #0F6E5B; }
        .score-mid { color: #B3541E; }
        .score-bad { color: #A3352B; }

        div[data-testid="stMetricValue"] { font-family: 'Space Grotesk', sans-serif; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def score_color_class(score):
    if score >= 75:
        return "score-good"
    elif score >= 45:
        return "score-mid"
    return "score-bad"


# ------------------------- Setup -------------------------

@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception:
        return None


def init_stripe():
    try:
        stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]
        return True
    except Exception:
        return False


supabase: Client = init_supabase()
stripe_ready = init_stripe()

if "user" not in st.session_state:
    st.session_state.user = None
if "view" not in st.session_state:
    st.session_state.view = "Audit Tool"


# ------------------------- Auth UI -------------------------

def show_auth_ui():
    st.title("🏪 Local Business Audit Tool")
    st.caption("Log in or sign up to start your free 7-day trial — no card required.")

    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log In", type="primary"):
                if not EMAIL_REGEX_SIMPLE.match(email):
                    st.error("Please enter a valid email address.")
                else:
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state.user = res.user
                        st.rerun()
                    except Exception:
                        st.error("Login failed. Check your email/password, or sign up first.")

    with tab_signup:
        with st.form("signup_form"):
            email2 = st.text_input("Email", key="signup_email")
            password2 = st.text_input("Password (at least 6 characters)", type="password", key="signup_password")
            if st.form_submit_button("Sign Up", type="primary"):
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


# ------------------------- Profile / trial / subscription -------------------------

def get_or_create_profile(user):
    resp = supabase.table("profiles").select("*").eq("id", user.id).execute()
    if resp.data:
        return resp.data[0]
    trial_end = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    new_profile = {"id": user.id, "email": user.email, "trial_end": trial_end, "subscription_status": "trialing"}
    supabase.table("profiles").insert(new_profile).execute()
    return new_profile


def has_access(profile):
    if not profile:
        return False, None
    if profile.get("subscription_status") == "active":
        return True, "active"
    trial_end_raw = profile.get("trial_end")
    if trial_end_raw:
        te = datetime.fromisoformat(trial_end_raw.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if now < te:
            days_left = (te - now).days
            return True, f"trial ({days_left}d left)"
    return False, "expired"


def create_checkout_session(user_email):
    app_url = st.secrets.get("APP_URL", "")
    price_id = st.secrets.get("STRIPE_PRICE_ID", "")
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=user_email,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{app_url}?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{app_url}?checkout=cancelled",
    )
    return session


def handle_checkout_return(user_id):
    params = st.query_params
    if params.get("checkout") == "success" and params.get("session_id"):
        session_id = params.get("session_id")
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.status == "complete":
                supabase.table("profiles").update({
                    "subscription_status": "active",
                    "stripe_customer_id": session.customer,
                    "stripe_subscription_id": session.subscription,
                }).eq("id", user_id).execute()
                st.query_params.clear()
                st.success("🎉 Subscription activated! Welcome aboard.")
                time.sleep(1.5)
                st.rerun()
        except Exception as e:
            st.error(f"Could not verify payment: {e}")


def show_subscribe_screen(user):
    st.title("🏪 Local Business Audit Tool")
    st.warning("Your free trial has ended. Subscribe to keep using the tool.")
    st.markdown("### Local Audit Tool — Pro Plan")
    st.markdown("Unlimited local business audits, website health reports, and outreach tools.")

    if stripe_ready and st.secrets.get("STRIPE_PRICE_ID"):
        if st.button("Subscribe Now", type="primary"):
            try:
                session = create_checkout_session(user.email)
                st.link_button("Complete payment", session.url, type="primary")
            except Exception as e:
                st.error(f"Could not start checkout: {e}")
    else:
        st.info("Payments are not configured yet.")

    if st.button("Log Out"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()


# ------------------------- Free data source: OpenStreetMap -------------------------

def search_business(query, max_results=5):
    """Search businesses using OpenStreetMap's free Nominatim API. No API key or billing needed."""
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "extratags": 1,
        "limit": max_results,
    }
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=NOMINATIM_HEADERS, timeout=15)
        time.sleep(1)  # respect Nominatim's 1 request/second usage policy
        return resp.json()
    except Exception:
        return []


def parse_business_result(result):
    extratags = result.get("extratags", {}) or {}
    address = result.get("address", {}) or {}
    name = result.get("name") or result.get("display_name", "").split(",")[0]
    website = extratags.get("website") or extratags.get("contact:website", "")
    phone = extratags.get("phone") or extratags.get("contact:phone", "")
    opening_hours = extratags.get("opening_hours", "")
    return {
        "name": name,
        "formatted_address": result.get("display_name", ""),
        "website": website,
        "phone": phone,
        "opening_hours": opening_hours,
    }


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


def compute_health_score(business, pagespeed, onpage):
    """Weights rebalanced since OSM data has no ratings field (unlike Google)."""
    score = 0
    max_score = 0
    max_score += 20
    if business.get("website"):
        score += 10
    if business.get("phone"):
        score += 5
    if business.get("opening_hours"):
        score += 5
    for key in ["performance", "seo", "accessibility", "best_practices"]:
        max_score += 12.5
        val = pagespeed.get(key)
        if val is not None:
            score += (val / 100) * 12.5
    for key in ["https", "title_tag", "meta_description", "mobile_viewport"]:
        max_score += 7.5
        if onpage.get(key):
            score += 7.5
    if max_score == 0:
        return 0
    return round((score / max_score) * 100)


# ------------------------- Email outreach -------------------------

def default_email_template(business_name, health_score):
    subject = f"Quick note about {business_name}'s online presence"
    body = (
        f"Hi there,\n\n"
        f"I ran a quick audit of {business_name}'s online presence and found a few "
        f"opportunities to improve your visibility online — your current score is "
        f"{health_score}/100.\n\n"
        f"I help local businesses fix exactly these kinds of issues (website speed, "
        f"SEO basics, online listings) so more customers find you.\n\n"
        f"Would you be open to a quick 10-minute call this week to walk through what "
        f"I found?\n\n"
        f"Best,\n"
        f"[Your Name]"
    )
    return subject, body


def send_email_smtp(to_email, subject, body):
    gmail_address = st.secrets.get("GMAIL_ADDRESS", "")
    gmail_password = st.secrets.get("GMAIL_APP_PASSWORD", "")
    if not gmail_address or not gmail_password:
        raise Exception("Gmail is not configured in secrets.")
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = to_email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, [to_email], msg.as_string())


def log_outreach_email(user_id, business_name, recipient_email, subject, body, health_score):
    supabase.table("outreach_emails").insert({
        "user_id": user_id,
        "business_name": business_name,
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "health_score": health_score,
        "status": "sent",
    }).execute()


def show_outreach_form(user_id, business_name, health_score):
    with st.expander("Send Outreach Email to This Business"):
        default_subject, default_body = default_email_template(business_name, health_score)
        recipient = st.text_input("Recipient email address", key=f"recipient_{business_name}")
        subject = st.text_input("Subject", value=default_subject, key=f"subject_{business_name}")
        body = st.text_area("Message", value=default_body, height=220, key=f"body_{business_name}")
        if st.button("Send Email", key=f"send_{business_name}"):
            if not EMAIL_REGEX_SIMPLE.match(recipient):
                st.error("Please enter a valid recipient email address.")
            else:
                try:
                    send_email_smtp(recipient, subject, body)
                    log_outreach_email(user_id, business_name, recipient, subject, body, health_score)
                    st.success(f"Email sent to {recipient} and logged!")
                except Exception as e:
                    st.error(f"Could not send email: {e}")


# ------------------------- Outreach log screen -------------------------

def show_outreach_log(user_id):
    st.title("Outreach Log")
    st.caption("Every email you've sent. Update the status as you hear back.")

    resp = supabase.table("outreach_emails").select("*").eq("user_id", user_id).order("sent_at", desc=True).execute()
    emails = resp.data

    if not emails:
        st.info("No outreach emails sent yet. Run an audit and send an email to see it here.")
        return

    for e in emails:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.write(f"**{e.get('business_name', '')}**")
                st.caption(f"To: {e.get('recipient_email', '')}")
                st.caption(f"Subject: {e.get('subject', '')}")
            with col2:
                st.write(f"Score: {e.get('health_score', 'N/A')}/100")
                sent_at = e.get("sent_at", "")
                st.caption(f"Sent: {sent_at[:10] if sent_at else ''}")
            with col3:
                current_status = e.get("status", "sent")
                new_status = st.selectbox(
                    "Status", STATUS_OPTIONS,
                    index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0,
                    key=f"status_{e['id']}",
                    label_visibility="collapsed",
                )
                if new_status != current_status:
                    supabase.table("outreach_emails").update({"status": new_status}).eq("id", e["id"]).execute()
                    st.rerun()


# ------------------------- Bulk audit mode -------------------------

def run_single_audit(business_query, pagespeed_api_key):
    results = search_business(business_query, max_results=1)
    if not results:
        return None
    business = parse_business_result(results[0])
    website = business.get("website", "")
    pagespeed = get_pagespeed_scores(website, pagespeed_api_key) if website else {}
    onpage = check_onpage_basics(website) if website else {}
    health_score = compute_health_score(business, pagespeed, onpage)
    return {
        "Business Name": business.get("name", ""),
        "Address": business.get("formatted_address", ""),
        "Phone": business.get("phone", ""),
        "Website": website,
        "Health Score": health_score,
    }


def show_bulk_audit(user, pagespeed_api_key):
    st.title("Bulk Audit Mode")
    st.caption("Upload a CSV of businesses and audit them all at once. Uses the free OpenStreetMap data source.")

    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if not uploaded:
        st.info("CSV should have at least a business name column. A location column and an email column are optional but recommended.")
        return

    df_input = pd.read_csv(uploaded)
    st.write("Preview:")
    st.dataframe(df_input.head(), use_container_width=True)

    cols = list(df_input.columns)
    col1, col2, col3 = st.columns(3)
    with col1:
        name_col = st.selectbox("Business name column", cols)
    with col2:
        location_col = st.selectbox("Location column (optional)", ["(none)"] + cols)
    with col3:
        email_col = st.selectbox("Email column (optional, for outreach)", ["(none)"] + cols)

    max_rows = st.slider("How many rows to audit", 1, min(50, len(df_input)), min(10, len(df_input)))

    if st.button("Run Bulk Audit", type="primary"):
        rows_to_process = df_input.head(max_rows)
        progress = st.progress(0.0, text="Starting...")
        results = []
        for i, row in rows_to_process.iterrows():
            name = str(row[name_col])
            location = str(row[location_col]) if location_col != "(none)" else ""
            query = f"{name} {location}".strip()
            try:
                result = run_single_audit(query, pagespeed_api_key)
            except Exception:
                result = None
            if result:
                if email_col != "(none)":
                    result["Email"] = row.get(email_col, "")
                results.append(result)
            progress.progress((i + 1) / len(rows_to_process), text=f"Audited {i + 1}/{len(rows_to_process)}")
        progress.empty()

        if not results:
            st.warning("No results. Try different column selections or a smaller/cleaner list.")
            return

        df_results = pd.DataFrame(results)
        st.session_state["bulk_results"] = df_results
        st.success(f"Audited {len(df_results)} businesses!")

    df_results = st.session_state.get("bulk_results")
    if df_results is not None:
        st.dataframe(df_results, use_container_width=True)
        csv = df_results.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Download Bulk Report (CSV)", data=csv, file_name="bulk_audit_report.csv", mime="text/csv")

        if "Email" in df_results.columns:
            st.divider()
            st.subheader("Bulk Outreach")
            threshold = st.slider("Send outreach to businesses with score below:", 0, 100, 60)
            low_score = df_results[(df_results["Health Score"] < threshold) & (df_results["Email"].notna()) & (df_results["Email"] != "")]
            st.write(f"{len(low_score)} businesses match (score below {threshold} and have an email).")
            if len(low_score) > 0 and st.button(f"Send outreach email to all {len(low_score)} businesses"):
                sent_count = 0
                for _, row in low_score.iterrows():
                    subject, body = default_email_template(row["Business Name"], row["Health Score"])
                    try:
                        send_email_smtp(row["Email"], subject, body)
                        log_outreach_email(user.id, row["Business Name"], row["Email"], subject, body, row["Health Score"])
                        sent_count += 1
                    except Exception:
                        pass
                st.success(f"Sent {sent_count}/{len(low_score)} outreach emails. Check the Outreach Log tab.")


# ------------------------- Main audit tool screen -------------------------

def show_audit_tool(user, access_label):
    with st.sidebar:
        st.success(f"Logged in as **{user.email}**")
        st.caption(f"Plan status: {access_label}")
        views = ["Audit Tool", "Bulk Audit", "Outreach Log"]
        st.session_state.view = st.radio("View", views, index=views.index(st.session_state.view) if st.session_state.view in views else 0)
        if st.button("Log Out"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()
        st.divider()
        st.header("Settings")
        st.caption("Business search uses the free OpenStreetMap data source — no key needed.")
        pagespeed_api_key = st.text_input("PageSpeed API Key (optional, free)", type="password")

    if st.session_state.view == "Outreach Log":
        show_outreach_log(user.id)
        return

    if st.session_state.view == "Bulk Audit":
        show_bulk_audit(user, pagespeed_api_key)
        return

    st.title("Local Business Audit Tool")
    st.caption("Free business search (OpenStreetMap) + website health check — no billing required.")

    query = st.text_input("Business name + location", placeholder="e.g. Joe's Pizza, Brooklyn")
    run = st.button("Run Audit", type="primary")

    if run:
        if not query:
            st.error("Please enter a business name and location.")
        else:
            with st.spinner("Searching for the business..."):
                results = search_business(query)
            if not results:
                st.warning("No results found. Try a different name or location.")
            else:
                st.session_state["last_results"] = results

    results = st.session_state.get("last_results")
    if results:
        options = {}
        for r in results[:5]:
            b = parse_business_result(r)
            options[f"{b['name']} — {b['formatted_address'][:60]}"] = b
        chosen_label = st.selectbox("Select the correct business:", list(options.keys()))
        business = options[chosen_label]

        if st.button("Run Full Audit on Selected Business"):
            with st.spinner("Running full audit..."):
                website = business.get("website", "")
                pagespeed = get_pagespeed_scores(website, pagespeed_api_key) if website else {}
                onpage = check_onpage_basics(website) if website else {}
                health_score = compute_health_score(business, pagespeed, onpage)
            st.session_state["last_audit"] = {
                "business": business, "website": website, "pagespeed": pagespeed,
                "onpage": onpage, "health_score": health_score,
            }

    audit = st.session_state.get("last_audit")
    if audit:
        business = audit["business"]
        website = audit["website"]
        pagespeed = audit["pagespeed"]
        onpage = audit["onpage"]
        health_score = audit["health_score"]

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(
                f"""<div class="score-card">
                <div style="font-size:0.85rem;color:#6B7280;">Health Score</div>
                <div class="score-number {score_color_class(health_score)}">{health_score}</div>
                <div style="font-size:0.85rem;color:#6B7280;">out of 100</div>
                </div>""",
                unsafe_allow_html=True,
            )
        with col2:
            st.write(f"**{business.get('name', '')}**")
            st.write(business.get("formatted_address", ""))

        st.divider()
        st.subheader("Business Listing")
        listing_rows = [
            ("Website listed", "Yes" if business.get("website") else "No"),
            ("Phone number listed", "Yes" if business.get("phone") else "No"),
            ("Opening hours set", "Yes" if business.get("opening_hours") else "No"),
        ]
        st.table(pd.DataFrame(listing_rows, columns=["Check", "Status"]))

        if website:
            st.subheader("Website Technical Health")
            ps_cols = st.columns(4)
            labels = {"performance": "Performance", "seo": "SEO", "accessibility": "Accessibility", "best_practices": "Best Practices"}
            for i, key in enumerate(["performance", "seo", "accessibility", "best_practices"]):
                val = pagespeed.get(key)
                ps_cols[i].metric(labels[key], f"{val}/100" if val is not None else "N/A")

            st.subheader("On-Page Basics")
            onpage_rows = [
                ("HTTPS (secure)", "Yes" if onpage.get("https") else "No"),
                ("Title tag present", "Yes" if onpage.get("title_tag") else "No"),
                ("Meta description present", "Yes" if onpage.get("meta_description") else "No"),
                ("Mobile-friendly viewport tag", "Yes" if onpage.get("mobile_viewport") else "No"),
            ]
            st.table(pd.DataFrame(onpage_rows, columns=["Check", "Status"]))
        else:
            st.warning("This business doesn't have a website listed — that's a great opportunity to pitch them!")

        st.divider()
        report_data = {
            "Business Name": [business.get("name", "")],
            "Address": [business.get("formatted_address", "")],
            "Phone": [business.get("phone", "")],
            "Website": [website],
            "Health Score": [health_score],
        }
        df_report = pd.DataFrame(report_data)
        csv = df_report.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Download Audit Report (CSV)", data=csv,
                            file_name=f"audit_{business.get('name', 'business').replace(' ', '_')}.csv",
                            mime="text/csv")

        st.divider()
        show_outreach_form(user.id, business.get("name", "this business"), health_score)


# ------------------------- Main -------------------------

inject_custom_css()

if supabase is None:
    st.error("Supabase is not configured. Please check your secrets.")
    st.stop()

if st.session_state.user is None:
    show_auth_ui()
    st.stop()

user = st.session_state.user
handle_checkout_return(user.id)
profile = get_or_create_profile(user)
allowed, access_label = has_access(profile)

if allowed:
    show_audit_tool(user, access_label)
else:
    show_subscribe_screen(user)
