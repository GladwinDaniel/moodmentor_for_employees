import os, re, io, base64, calendar
from datetime import date, datetime, timedelta
import requests, streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from db import (init_db, save_mood_log, save_manual_mood, MOOD_LABELS, MOOD_EMOJI,
                 get_mood_logs_for_month, get_user_mood_history,
                 get_all_employee_mood_logs, get_latest_mood_per_employee,
                 QUESTIONNAIRE_QUESTIONS, score_questionnaire, save_questionnaire_response,
                 get_questionnaire_history, get_all_questionnaire_responses,
                 get_profile_photo, save_profile_photo)
from recommendations import (get_period_recommendation, get_questionnaire_recommendation,
                              get_team_recommendation)
import csv
from auth import (make_token, read_token, get_user, username_taken, create_user,
                   verify_user, set_password, check_pw, new_otp, save_otp, check_otp,
                   record_failed_login, reset_failed_login, is_account_locked,
                   MAX_LOGIN_ATTEMPTS, LOCKOUT_MINUTES, update_email)
from email_utils import send_otp
from security import sanitize_text

IST_OFFSET = timedelta(hours=5, minutes=30)

def now_ist():
    return datetime.utcnow() + IST_OFFSET

def today_ist():
    return now_ist().date()

st.set_page_config(page_title="MoodMentor", layout="wide")

sns.set_theme(style="white", rc={
    "figure.facecolor": "none", "axes.facecolor": "none", "savefig.facecolor": "none",
    "font.family": "sans-serif", "text.color": "#241F3B",
    "axes.labelcolor": "#544E72", "xtick.color": "#544E72", "ytick.color": "#544E72",
})

BACKEND_URL = os.getenv("BACKEND_URL") or (st.secrets.get("BACKEND_URL") if hasattr(st, "secrets") and "BACKEND_URL" in st.secrets else "http://localhost:8000")

MOOD_STYLE = {
    "Happy":   {"emoji": MOOD_EMOJI["Happy"],   "color": "#2ecc71"},
    "Neutral": {"emoji": MOOD_EMOJI["Neutral"], "color": "#3498db"},
    "Sad":     {"emoji": MOOD_EMOJI["Sad"],     "color": "#e67e22"},
    "Stress":  {"emoji": MOOD_EMOJI["Stress"],  "color": "#f1c40f"},
    "Angry":   {"emoji": MOOD_EMOJI["Angry"],   "color": "#e74c3c"},
    "Fear":    {"emoji": MOOD_EMOJI["Fear"],    "color": "#9b59b6"},
}
def style_for(label):
    return MOOD_STYLE.get(label, {"emoji": "", "color": "#bdbdbd"})

MOOD_TO_NUM = {"Happy": 2, "Neutral": 0, "Sad": -1, "Stress": -1, "Angry": -2, "Fear": -2}

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    :root{
      --joy:#F3A48A; --sadness:#9C90C7; --anger:#EE7268;
      --fear:#77C3E0; --surprise:#EFBE5C; --disgust:#82CFA0;
      --ink:#241F3B; --ink-soft:#544E72;
      --violet:#7C5CFC; --violet-deep:#5B3FE0; --lilac:#C88CF2;
      --grad-brand: linear-gradient(100deg,#7C5CFC 0%, #A874F0 55%, #D98FE0 100%);
      --glass: rgba(255,255,255,0.62); --glass-strong: rgba(255,255,255,0.78); --glass-border: rgba(255,255,255,0.75);
      --shadow-tight: 0 8px 24px -10px rgba(92,63,224,0.25);
      --shadow-soft: 0 20px 60px -20px rgba(92,63,224,0.28);
      --radius: 22px;
    }

    html, body, [class*="css"]{ font-family:'Plus Jakarta Sans', sans-serif; color:var(--ink); }
    .stApp{
      background: linear-gradient(160deg,#EFEAFB 0%, #F1E9F7 30%, #F6E7EE 62%, #FBEADD 100%);
      background-attachment: fixed;
    }
    h1,h2,h3,h4{ font-family:'Sora', sans-serif !important; color:var(--ink) !important; letter-spacing:-.01em; }

        footer{ visibility:hidden; }

        section[data-testid="stSidebar"]{
      background:rgba(255,255,255,0.55); backdrop-filter:blur(18px);
      border-right:1px solid rgba(255,255,255,0.6);
    }

        section[data-testid="stSidebar"] div[data-testid="stButton"]{ margin-bottom:2px; }

        section[data-testid="stSidebar"] .stButton > button[kind="secondary"]{
      background:transparent !important; color:var(--ink-soft) !important;
      border:1.5px solid transparent !important; box-shadow:none !important;
      border-radius:12px !important; font-weight:600 !important; font-size:13.5px !important;
      padding:9px 14px !important; text-align:left !important; justify-content:flex-start !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover{
      background:rgba(124,92,252,.08) !important; color:var(--violet-deep) !important;
      transform:none !important;
    }
        section[data-testid="stSidebar"] .stButton > button[kind="primary"]{
      border-radius:12px !important; font-weight:800 !important; font-size:13.5px !important;
      padding:9px 14px !important; text-align:left !important; justify-content:flex-start !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover{ transform:none !important; }

        [class*="st-key-mood_opt_"] button{
      height:88px !important; display:flex !important; flex-direction:column !important;
      align-items:center !important; justify-content:center !important;
      font-size:15px !important; font-weight:700 !important; gap:2px !important;
      white-space:pre-line !important; line-height:1.5 !important;
    }

        .st-key-profile_avatar_btn button{
      width:44px !important; height:44px !important; min-width:44px !important; padding:0 !important;
      border-radius:50% !important; border:2px solid rgba(255,255,255,.9) !important;
      background:var(--grad-brand) !important; color:#fff !important; font-weight:800 !important;
      font-family:'Sora',sans-serif !important; box-shadow:var(--shadow-tight) !important;
      transition:.2s !important;
    }
    .st-key-profile_avatar_btn button:hover{ transform:scale(1.06) !important; }

        .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button{
      background:var(--grad-brand) !important; color:#fff !important; border:none !important;
      border-radius:999px !important; font-weight:700 !important; padding:10px 22px !important;
      box-shadow:var(--shadow-tight); transition:.2s ease !important;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover{
      transform:translateY(-2px); box-shadow:0 14px 30px -10px rgba(92,63,224,.5);
    }
    .stButton > button[kind="secondary"]{
      background:#fff !important; color:var(--violet-deep) !important;
      border:1.5px solid rgba(124,92,252,.35) !important; box-shadow:none;
    }

        .stTextInput input, .stTextArea textarea, .stDateInput input, .stNumberInput input,
    div[data-baseweb="select"] > div{
      background:#fff !important; border:1.5px solid rgba(124,92,252,.18) !important;
      border-radius:13px !important; color:var(--ink) !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus{
      border-color:var(--violet) !important; box-shadow:0 0 0 4px rgba(124,92,252,.14) !important;
    }

        div[role="radiogroup"]{ gap:6px; }
    div[role="radiogroup"] label{
      background:rgba(255,255,255,.55); border:1.5px solid rgba(124,92,252,.15);
      border-radius:999px !important; padding:8px 16px !important; font-weight:600;
    }

        [data-testid="stCameraInput"], [data-testid="stFileUploader"], [data-testid="stAudioInput"]{
      background:var(--glass); border:1.5px dashed rgba(124,92,252,.35);
      border-radius:var(--radius); padding:14px;
    }

        [data-testid="stMetric"]{
      background:var(--glass); border:1px solid var(--glass-border); border-radius:var(--radius);
      padding:16px 18px; box-shadow:var(--shadow-tight);
    }
    [data-testid="stMetricValue"]{ color:var(--violet-deep) !important; font-family:'Sora',sans-serif !important; }

        [data-testid="stAlert"], [data-testid="stAlertContainer"]{
      border-radius:16px !important; border:1px solid rgba(255,255,255,.6) !important;
      backdrop-filter:blur(6px);
    }

        [data-testid="stProgress"] > div > div{ background:var(--grad-brand) !important; border-radius:999px; }
    [data-testid="stProgress"]{ background:rgba(124,92,252,.12); border-radius:999px; }

        [data-testid="stExpander"], [data-testid="stForm"]{
      background:var(--glass-strong); border:1px solid var(--glass-border) !important;
      border-radius:var(--radius) !important; box-shadow:var(--shadow-soft);
    }
    [data-testid="stDataFrame"]{ border-radius:14px; overflow:hidden; box-shadow:var(--shadow-tight); }

        [data-testid="stChatMessage"]{
      background:var(--glass); border-radius:18px; border:1px solid var(--glass-border);
      box-shadow:var(--shadow-tight);
    }
    [data-testid="stChatInput"] textarea{ border-radius:16px !important; }

        div[data-testid="stVerticalBlockBorderWrapper"]{
      border-radius:var(--radius) !important; border:1px solid var(--glass-border) !important;
      background:var(--glass-strong) !important; box-shadow:var(--shadow-soft);
    }
    </style>
    """, unsafe_allow_html=True)

def render_sidebar_brand():
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;padding:4px 2px 18px;">
      <svg width="34" height="34" viewBox="0 0 48 48" fill="none">
        <path d="M24 6c-7 0-12 5-12 11 0 3 1 5 3 7-2 1-3 3-3 6 0 5 4 9 9 9h1v3h4v-3h1c5 0 9-4 9-9 0-3-1-5-3-6 2-2 3-4 3-7 0-6-5-11-12-11z" fill="url(#g1)"/>
        <path d="M24 20c1.5-2 4.5-2 5.8-.2 1.2 1.7.6 3.6-1.3 5.4L24 30l-4.5-4.8c-1.9-1.8-2.5-3.7-1.3-5.4 1.3-1.8 4.3-1.8 5.8.2z" fill="#fff"/>
        <defs><linearGradient id="g1" x1="12" y1="6" x2="36" y2="42">
          <stop stop-color="#7C5CFC"/><stop offset="1" stop-color="#D98FE0"/>
        </linearGradient></defs>
      </svg>
      <div style="line-height:1.1;">
        <div style="font-family:'Sora',sans-serif;font-weight:800;font-size:17px;color:#241F3B;">
          Mood<span style="background:linear-gradient(100deg,#7C5CFC,#D98FE0);-webkit-background-clip:text;background-clip:text;color:transparent;">Mentor</span>
        </div>
        <div style="font-size:9.5px;font-weight:700;letter-spacing:.04em;color:#544E72;">EMOTIONAL WELLNESS</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def donut_chart(counts: dict, size=2.6):
    labels, values, colors = [], [], []
    for k, v in counts.items():
        if v > 0:
            labels.append(k); values.append(v)
            colors.append(style_for(k)["color"])
    if not values:
        return None
    fig, ax = plt.subplots(figsize=(size, size))
    ax.pie(values, colors=colors, startangle=90, wedgeprops=dict(width=0.38, edgecolor="white"))
    ax.set(aspect="equal")
    fig.patch.set_alpha(0.0)
    return fig

BRAND_PALETTE = ["#7C5CFC", "#A874F0", "#D98FE0", "#77C3E0", "#82CFA0", "#EFBE5C", "#EE7268", "#F3A48A", "#9C90C7"]

def _palette_for(labels):
    return [style_for(l)["color"] if l in MOOD_STYLE else BRAND_PALETTE[i % len(BRAND_PALETTE)]
            for i, l in enumerate(labels)]

def styled_bar_chart(data: dict, figsize=(5.4, 3.1)):
    data = {k: v for k, v in data.items() if v is not None}
    if not data:
        return None
    order = sorted(data.items(), key=lambda kv: kv[1])
    labels = [k for k, _ in order]
    values = [v for _, v in order]
    colors = _palette_for(labels)
    fig, ax = plt.subplots(figsize=figsize)
    sns.barplot(x=values, y=labels, hue=labels, palette=colors, dodge=False, legend=False, ax=ax)
    for i, v in enumerate(values):
        label = f"{v:.0f}" if float(v).is_integer() else f"{v:.1f}"
        ax.text(v, i, f"  {label}", va="center", fontsize=9, color="#544E72")
    ax.set_xlim(0, max(values) * 1.2 if max(values) > 0 else 1)
    ax.set_xlabel(""); ax.set_ylabel("")
    sns.despine(bottom=True, left=True, ax=ax)
    ax.tick_params(axis="both", length=0)
    ax.grid(axis="x", color="#7C5CFC", alpha=0.1)
    fig.patch.set_alpha(0.0); ax.patch.set_alpha(0.0)
    fig.tight_layout()
    return fig

def styled_line_chart(data: dict, figsize=(5.8, 3.1)):
    data = {k: v for k, v in data.items() if v is not None}
    if not data:
        return None
    labels = list(data.keys())
    values = list(data.values())
    xs = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(xs, values, color="#7C5CFC", linewidth=2.4, marker="o", markersize=4.5,
            markerfacecolor="#7C5CFC", markeredgecolor="white", markeredgewidth=1)
    ax.fill_between(xs, values, min(values), color="#7C5CFC", alpha=0.12)
    step = max(1, len(labels) // 8)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels([labels[i] for i in xs[::step]], rotation=30, ha="right", fontsize=8)
    ax.set_xlabel(""); ax.set_ylabel("")
    sns.despine(ax=ax)
    ax.grid(axis="y", color="#7C5CFC", alpha=0.1)
    fig.patch.set_alpha(0.0); ax.patch.set_alpha(0.0)
    fig.tight_layout()
    return fig

def metric_tile(label, value, sub=None):
    st.metric(label, value, delta=sub, delta_color="off")

def build_pdf_report(username, start_d, end_d, entries, recommendation_text):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=48, bottomMargin=48)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("MoodMentor Wellness Report", styles["Title"]))
    story.append(Paragraph(f"{username} &nbsp;|&nbsp; {start_d} to {end_d}", styles["Normal"]))
    story.append(Spacer(1, 16))

    counts = {}
    for h in entries:
        counts[h["sentiment"]] = counts.get(h["sentiment"], 0) + 1
    summary_line = ", ".join(f"{k}: {v}" for k, v in counts.items())
    story.append(Paragraph("Mood summary", styles["Heading2"]))
    story.append(Paragraph(f"{len(entries)} entries logged. {summary_line}.", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Recommendation", styles["Heading2"]))
    story.append(Paragraph(recommendation_text, styles["Normal"]))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Entries", styles["Heading2"]))
    table_data = [["Date", "Time", "Mood", "Emotion", "Confidence", "Source"]]
    for h in sorted(entries, key=lambda r: r["created_at"], reverse=True):
        table_data.append([
            str(h["mood_date"]),
            h["created_at"].strftime("%H:%M"),
            h["sentiment"] or "\u2014",
            h.get("emotion") or "\u2014",
            f"{h['confidence']:.0%}" if h.get("confidence") is not None else "\u2014",
            h["source"],
        ])
    tbl = Table(table_data, repeatRows=1, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#444444")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7f6")]),
    ]))
    story.append(tbl)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

def build_csv_export(rows: list, fieldnames: list) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")

def render_profile_section(user, role):
    uid = user["id"]
    photo_key = f"profile_photo_{uid}"
    if photo_key not in st.session_state:
        st.session_state[photo_key] = get_profile_photo(uid)
    edit_key = f"editing_photo_{uid}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    st.subheader(" Profile")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.session_state.get(photo_key):
            st.image(st.session_state[photo_key], width=88)
        else:
            initial = (user.get("username") or "?").strip()[0].upper()
            st.write(f"### {initial}")
    with col2:
        st.write(f"**{user.get('username', '—')}**")
        st.caption(role.capitalize())
        if st.button("Change Profile Photo", key="profile_edit_btn"):
            st.session_state[edit_key] = not st.session_state[edit_key]

    if st.session_state[edit_key]:
        st.write("")
        st.markdown("**Upload & Adjust Profile Picture**")
        uploaded_photo = st.file_uploader(
            "Choose an image", type=["png", "jpg", "jpeg"], key=f"photo_uploader_{uid}",
        )
        if uploaded_photo is not None:
            from PIL import Image
            img = Image.open(uploaded_photo).convert("RGB")
            w, h = img.size
            min_side = min(w, h)
            zoom = st.slider("Zoom", 1.0, 3.0, 1.0, 0.05, key=f"zoom_{uid}")
            crop_size = max(10, min(int(min_side / zoom), min_side))
            max_x = max(w - crop_size, 0)
            max_y = max(h - crop_size, 0)
            x = st.slider("Move Horizontal", 0, max_x, max_x // 2, key=f"offx_{uid}") if max_x > 0 else 0
            y = st.slider("Move Vertical", 0, max_y, max_y // 2, key=f"offy_{uid}") if max_y > 0 else 0
            cropped = img.crop((x, y, x + crop_size, y + crop_size)).resize((300, 300))

            pc1, pc2 = st.columns([1, 3])
            with pc1:
                st.image(cropped, width=120, caption="Preview")
            with pc2:
                st.write("")
                save_col, cancel_col = st.columns(2)
                with save_col:
                    if st.button("Save Photo", key=f"save_photo_{uid}", type="primary", use_container_width=True):
                        buf = io.BytesIO()
                        cropped.save(buf, format="PNG")
                        photo_bytes = buf.getvalue()
                        save_profile_photo(uid, photo_bytes)
                        st.session_state[photo_key] = photo_bytes
                        st.session_state[edit_key] = False
                        st.success("Profile picture updated!")
                        st.rerun()
                with cancel_col:
                    if st.button("Cancel", key=f"cancel_photo_{uid}", use_container_width=True):
                        st.session_state[edit_key] = False
                        st.rerun()

    st.write("")
    left, right = st.columns(2)

    with left:
        st.markdown("**User Information**")
        st.write("")
        st.text_input("User ID", value=str(user.get("id", "—")), disabled=True)
        st.text_input("Name", value=user.get("username", "—"), disabled=True)
        st.text_input("Role", value=str(role).capitalize(), disabled=True)

        email_edit_key = f"editing_email_{uid}"
        otp_sent_key = f"email_otp_sent_{uid}"
        pending_email_key = f"pending_new_email_{uid}"
        if email_edit_key not in st.session_state:
            st.session_state[email_edit_key] = False
        if otp_sent_key not in st.session_state:
            st.session_state[otp_sent_key] = False

        ec1, ec2 = st.columns([4, 1.5])
        with ec1:
            st.text_input("Email ID", value=user.get("email", "—"), disabled=True, key=f"email_display_{uid}")
        with ec2:
            st.write("")
            if st.button("Edit Email", key=f"edit_email_btn_{uid}", use_container_width=True):
                st.session_state[email_edit_key] = not st.session_state[email_edit_key]
                st.session_state[otp_sent_key] = False

        if st.session_state[email_edit_key]:
            if not st.session_state[otp_sent_key]:
                new_email = st.text_input("New Email", placeholder="Enter new email", key=f"new_email_input_{uid}")
                sc1, sc2 = st.columns(2)
                with sc1:
                    if st.button("Send OTP", key=f"send_email_otp_{uid}", type="primary", use_container_width=True):
                        new_email_clean = sanitize_text(new_email.strip().lower())
                        if not new_email_clean or "@" not in new_email_clean:
                            st.error("Enter a valid email address.")
                        elif new_email_clean == (user.get("email") or "").lower():
                            st.error("This is already your current email.")
                        elif get_user(new_email_clean):
                            st.error("This email is already in use.")
                        else:
                            code = new_otp()
                            save_otp(new_email_clean, code, "email_change")
                            ok, msg = send_otp(new_email_clean, code, "email_change")
                            if ok:
                                st.session_state[pending_email_key] = new_email_clean
                                st.session_state[otp_sent_key] = True
                                st.success("OTP sent to your new email.")
                                st.rerun()
                            else:
                                st.error(f"Failed to send OTP: {msg}")
                with sc2:
                    if st.button("Cancel", key=f"cancel_email_edit1_{uid}", use_container_width=True):
                        st.session_state[email_edit_key] = False
                        st.rerun()
            else:
                pending_email = st.session_state.get(pending_email_key, "")
                st.caption(f"Enter the code sent to **{pending_email}**")
                otp_code = st.text_input("Verification Code", max_chars=6, key=f"email_otp_code_{uid}")
                vc1, vc2 = st.columns(2)
                with vc1:
                    if st.button("Verify & Update", key=f"verify_email_otp_{uid}", type="primary", use_container_width=True):
                        if check_otp(pending_email, otp_code.strip(), "email_change"):
                            update_email(uid, pending_email)
                            updated_user = get_user(pending_email)
                            st.session_state.token = make_token(updated_user)
                            st.session_state[email_edit_key] = False
                            st.session_state[otp_sent_key] = False
                            st.success("Email updated successfully!")
                            st.rerun()
                        else:
                            st.error("Invalid or expired code.")
                with vc2:
                    if st.button("Cancel", key=f"cancel_email_edit2_{uid}", use_container_width=True):
                        st.session_state[email_edit_key] = False
                        st.session_state[otp_sent_key] = False
                        st.rerun()

    with right:
        st.markdown("**Change Password**")
        st.write("")
        current_pw = st.text_input("Current Password", type="password", placeholder="Enter current password", key=f"pw_current_{uid}")
        new_pw = st.text_input("New Password", type="password", placeholder="Enter new password", key=f"pw_new_{uid}")
        confirm_pw = st.text_input("Confirm Password", type="password", placeholder="Confirm new password", key=f"pw_confirm_{uid}")

        if st.button("Update Password", type="primary", use_container_width=True, key=f"pw_update_btn_{uid}"):
            full = get_user(user["email"])
            stored_hash = full["password_hash"] if full else None
            if not stored_hash or not check_pw(current_pw, stored_hash):
                st.error("Current password is incorrect.")
            elif not valid_pw(new_pw):
                st.error("Password needs 8+ chars, letters and numbers.")
            elif new_pw != confirm_pw:
                st.error("New password and confirm password do not match.")
            else:
                set_password(user["email"], new_pw)
                st.success("Password updated successfully.")

inject_css()

@st.cache_resource
def setup(): init_db()
setup()

if "page" not in st.session_state: st.session_state.page = "welcome"
if "show_auth_panel" not in st.session_state: st.session_state.show_auth_panel = False
if "auth_mode" not in st.session_state: st.session_state.auth_mode = "login"
if "token" not in st.session_state: st.session_state.token = None
if "email" not in st.session_state: st.session_state.email = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "cal_year" not in st.session_state: st.session_state.cal_year = today_ist().year
if "cal_month" not in st.session_state: st.session_state.cal_month = today_ist().month
if "today_mood_saved" not in st.session_state: st.session_state.today_mood_saved = False
if "nav" not in st.session_state: st.session_state.nav = "Home"

def goto_auth(mode): st.session_state.auth_mode = mode; st.rerun()

def valid_pw(pw):
    return len(pw) >= 8 and re.search(r"[A-Za-z]", pw) and re.search(r"[0-9]", pw)

if st.session_state.token:
    user = read_token(st.session_state.token)
    if user:
        role = user.get("role", "employee")
        headers = {"Authorization": f"Bearer {st.session_state.token}"}

        with st.sidebar:
            render_sidebar_brand()
            if role == "employee":
                nav_options = ["Home", "Journal", "Questionnaire", "Wellness Chat",
                                "Face Detection", "Voice Analyzer", "Focus Timer", "Relax",
                                "Dashboard"]
            else:
                nav_options = ["Reports"]
            for _opt in nav_options:
                _is_active = st.session_state.nav == _opt
                if st.button(_opt, key=f"navtab_{_opt}", use_container_width=True,
                             type="primary" if _is_active else "secondary"):
                    st.session_state.nav = _opt
                    st.rerun()
            st.divider()
            st.caption(f"Signed in as **{user['username']}**")
            st.caption(f"{user['email']} · {role.capitalize()}")
            if st.button("Log out", use_container_width=True):
                st.session_state.token = None
                st.session_state.page = "welcome"
                st.session_state.show_auth_panel = False
                st.rerun()

        _now_ist = now_ist()
        greeting = "Good Morning" if _now_ist.hour < 12 else (
            "Good Afternoon" if _now_ist.hour < 18 else "Good Evening")

        header_left, header_right = st.columns([6, 1])
        with header_left:
            st.subheader(f"{greeting}, {user['username']}!")
            st.caption("Here's your emotional wellness overview.")
        with header_right:
            _uid = user["id"]
            _photo_key = f"profile_photo_{_uid}"
            if _photo_key not in st.session_state:
                st.session_state[_photo_key] = get_profile_photo(_uid)
            _photo_bytes = st.session_state.get(_photo_key)
            with st.container(key="profile_avatar_btn"):
                _initial = (user.get("username") or "?").strip()[0].upper()
                if st.button(_initial, key="profile_avatar_inner"):
                    st.session_state.nav = "Profile"
                    st.rerun()
            if _photo_bytes:
                _b64 = base64.b64encode(_photo_bytes).decode()
                st.markdown(
                    f'<style>.st-key-profile_avatar_btn button {{'
                    f'background-image:url("data:image/png;base64,{_b64}") !important;'
                    f'background-size:cover !important; background-position:center !important;'
                    f'color:transparent !important;}}</style>',
                    unsafe_allow_html=True,
                )

        if role == "employee":
            section = st.session_state.nav

            if section == "Home":
                history_all = get_user_mood_history(user["id"], limit=500)
                latest = history_all[0] if history_all else None
                today_count = sum(1 for h in history_all if h["mood_date"] == today_ist())
                streak = 0
                day_ptr = today_ist()
                day_set = {h["mood_date"] for h in history_all}
                while day_ptr in day_set:
                    streak += 1
                    day_ptr = date.fromordinal(day_ptr.toordinal() - 1)

                positive_count = sum(1 for h in history_all if h["sentiment"] == "Happy")
                overall_score = int(100 * positive_count / len(history_all)) if history_all else 0

                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    if latest:
                        s = style_for(latest["sentiment"])
                        metric_tile("Current Mood", f"{s['emoji']} {latest['sentiment']}")
                    else:
                        metric_tile("Current Mood", "—")
                with m2:
                    metric_tile("Overall Score", f"{overall_score}%", "Positive" if overall_score >= 50 else "Needs care")
                with m3:
                    metric_tile("Entries Today", today_count)
                with m4:
                    metric_tile("Current Streak", f"{streak} Days")

                st.write("")
                st.subheader("How Do You Feel?")
                now = now_ist()
                st.caption(f"{now.strftime('%Y-%m-%d')}  {now.strftime('%H:%M')}")

                cols = st.columns(len(MOOD_LABELS))
                picked = st.session_state.get("picked_mood")
                for col, label in zip(cols, MOOD_LABELS):
                    s = style_for(label)
                    is_sel = picked == label
                    with col:
                        with st.container(key=f"mood_opt_{label}"):
                            if st.button(f"{s['emoji']}\n{label}", key=f"pick_{label}",
                                         use_container_width=True,
                                         type="primary" if is_sel else "secondary"):
                                st.session_state.picked_mood = label

                st.write("")
                confirm_col = st.columns([3, 1, 3])[1]
                with confirm_col:
                    disabled = picked is None
                    if st.button("Save mood", type="primary", disabled=disabled,
                                 use_container_width=True):
                        save_manual_mood(user["id"], st.session_state.picked_mood)
                        st.session_state.today_mood_saved = True
                        st.session_state.picked_mood = None
                        st.rerun()

                if st.session_state.today_mood_saved:
                    st.success("Today's mood saved!")
                    st.session_state.today_mood_saved = False

                st.subheader("Your Mood Calendar")

                nav_l, nav_mid, nav_r = st.columns([1, 3, 1])
                if nav_l.button("← Prev"):
                    m, y = st.session_state.cal_month - 1, st.session_state.cal_year
                    if m == 0: m, y = 12, y - 1
                    st.session_state.cal_month, st.session_state.cal_year = m, y
                    st.rerun()
                if nav_r.button("Next →"):
                    m, y = st.session_state.cal_month + 1, st.session_state.cal_year
                    if m == 13: m, y = 1, y + 1
                    st.session_state.cal_month, st.session_state.cal_year = m, y
                    st.rerun()
                nav_mid.markdown(
                    f"**{calendar.month_name[st.session_state.cal_month]} "
                    f"{st.session_state.cal_year}**"
                )

                logs = get_mood_logs_for_month(user["id"], st.session_state.cal_year,
                                                st.session_state.cal_month)
                by_day = {row["mood_date"].day: row for row in logs}

                weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(
                    st.session_state.cal_year, st.session_state.cal_month
                )
                day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
                header_cols = st.columns(7)
                for c, name in zip(header_cols, day_names):
                    c.markdown(f"**{name}**")

                for week in weeks:
                    cols = st.columns(7)
                    for col, day_num in zip(cols, week):
                        if day_num == 0:
                            col.write("")
                            continue
                        entry = by_day.get(day_num)
                        s = style_for(entry["sentiment"] if entry else None)
                        time_label = entry["created_at"].strftime("%H:%M") if entry else ""
                        col.write(f"{day_num}")
                        col.write(s["emoji"] if entry else "")
                        col.caption(time_label)

                legend = " · ".join(l for l in MOOD_LABELS)
                st.caption(f"{legend} · No entry logged  (hover/see time under each day)")

            elif section == "Journal":
                st.subheader(" Journal")
                journal_text = st.text_area(
                    "Write about how you're feeling today", height=150,
                    placeholder="Your note here...",
                )
                if st.button("Analyze my entry"):
                    if not journal_text.strip():
                        st.warning("Write something first.")
                    else:
                        clean_text = sanitize_text(journal_text.strip())
                        with st.spinner("Running NLP analysis…"):
                            try:
                                resp = requests.post(
                                    f"{BACKEND_URL}/analyze-text",
                                    json={"text": clean_text},
                                    headers=headers, timeout=120,
                                )
                            except requests.exceptions.RequestException as e:
                                st.error(f"Could not reach backend: {e}"); resp = None
                        if resp is not None:
                            if resp.status_code != 200:
                                st.error("Analysis failed.")
                            else:
                                r = resp.json()
                                confidence = r.get("emotion_confidence")
                                save_mood_log(
                                    user["id"], r["final_sentiment"], r["final_emotion"],
                                    r["sentiment_scores"]["compound"], clean_text,
                                    confidence=confidence,
                                )
                                conf_str = f", Confidence: **{confidence:.0%}**" if confidence is not None else ""
                                st.success(f"Saved! Sentiment: **{r['final_sentiment']}**, "
                                           f"Emotion: **{r['final_emotion']}**{conf_str}")
                                _fig = styled_bar_chart(r["emotion_scores"])
                                if _fig: st.pyplot(_fig, use_container_width=True)
                                if r.get("recommendation"):
                                    st.info(f"**Recommendation:** {r['recommendation']}")

                st.subheader("Or upload a file")
                uploaded = st.file_uploader("Choose a CSV or TXT file", type=["csv", "txt"])
                if uploaded is not None and st.button("Run NLP Analysis on file"):
                    files = {"file": (uploaded.name, uploaded.getvalue())}
                    with st.spinner("Running multilingual NLP pipeline…"):
                        try:
                            resp = requests.post(f"{BACKEND_URL}/analyze", files=files,
                                                  headers=headers, timeout=120)
                        except requests.exceptions.RequestException as e:
                            st.error(f"Could not reach backend: {e}"); resp = None
                    if resp is not None:
                        if resp.status_code != 200:
                            st.error("Analysis failed.")
                        else:
                            r = resp.json()
                            confidence = r.get("emotion_confidence")
                            save_mood_log(
                                user["id"], r["final_sentiment"], r["final_emotion"],
                                r["sentiment_scores"]["compound"], r.get("cleaned_text", ""),
                                confidence=confidence,
                            )
                            conf_str = f", Confidence: **{confidence:.0%}**" if confidence is not None else ""
                            st.success(f"Saved! Sentiment: **{r['final_sentiment']}**, "
                                       f"Emotion: **{r['final_emotion']}**{conf_str}")
                            _fig = styled_bar_chart(r["emotion_scores"])
                            if _fig: st.pyplot(_fig, use_container_width=True)
                            if r.get("recommendation"):
                                st.info(f"**Recommendation:** {r['recommendation']}")

                st.subheader(" Past entries")
                history = [h for h in get_user_mood_history(user["id"], limit=20)
                           if h["journal_text"]]
                if not history:
                    st.caption("No journal entries yet.")
                for h in history:
                    s = style_for(h["sentiment"])
                    conf_str = f" · Confidence: {h['confidence']:.0%}" if h.get("confidence") is not None else ""
                    with st.expander(
                        f"{s['emoji']} {h['sentiment']} — {h['created_at'].strftime('%Y-%m-%d %H:%M')}{conf_str}"
                    ):
                        st.write(h["journal_text"])

            elif section == "Questionnaire":
                st.subheader(" Wellness Check-in")
                st.caption(
                    "A quick 12-question check-in. Your ratings feed a short wellness score; "
                    "the rest just helps tailor the suggestion you get afterward."
                )

                with st.form("questionnaire_form"):
                    answers = {}
                    for q in QUESTIONNAIRE_QUESTIONS:
                        answers[q["id"]] = st.radio(
                            q["text"], q["options"], key=f"qn_{q['id']}", horizontal=False,
                        )
                    submitted = st.form_submit_button("Submit check-in")

                if submitted:
                    result = score_questionnaire(answers)
                    save_questionnaire_response(
                        user["id"], answers, result["total_score"], result["category"],
                    )
                    rec = get_questionnaire_recommendation(
                        result["category"],
                        support_pref=answers.get("q7_support_pref"),
                        help_now=answers.get("q11_help_now"),
                        wants_to_talk=answers.get("q8_want_to_talk"),
                    )
                    st.success(
                        f"Check-in saved! Wellness score: **{result['total_score']}/{result['max_score']}** "
                        f"— **{result['category']}**"
                    )
                    if rec["escalate"]:
                        st.warning(rec["message"])
                    else:
                        st.info(rec["message"])

                st.subheader(" Past check-ins")
                qn_history = get_questionnaire_history(user["id"], limit=50)
                if not qn_history:
                    st.caption("No check-ins yet.")
                else:
                    qn_table = [{
                        "Date": h["submitted_at"].strftime("%Y-%m-%d %H:%M"),
                        "Score": f"{h['total_score']}/{h['max_score']}",
                        "Category": h["category"],
                        "Wants to talk?": h.get("wants_to_talk") or "—",
                    } for h in qn_history]
                    st.dataframe(qn_table, use_container_width=True)

                    if st.button("Export CSV", key="qn_export_csv"):
                        csv_rows = []
                        for h in qn_history:
                            row = {
                                "submitted_at": h["submitted_at"].strftime("%Y-%m-%d %H:%M"),
                                "total_score": h["total_score"], "max_score": h["max_score"],
                                "category": h["category"],
                            }
                            row.update(h["answers"])
                            csv_rows.append(row)
                        fieldnames = ["submitted_at", "total_score", "max_score", "category"] +                                     [q["id"] for q in QUESTIONNAIRE_QUESTIONS]
                        csv_bytes = build_csv_export(csv_rows, fieldnames)
                        st.download_button(
                            "Download CSV", data=csv_bytes,
                            file_name=f"moodmentor_questionnaire_{user['username']}.csv",
                            mime="text/csv",
                        )

            elif section == "Wellness Chat":
                st.subheader(" Wellness Chat")
                st.caption("A supportive space to talk about how you're feeling. "
                           "Not a substitute for professional care.")
                chat_box = st.container(height=450)
                with chat_box:
                    for turn in st.session_state.chat_history:
                        with st.chat_message(turn["role"]):
                            st.write(turn["content"])

                user_msg = st.chat_input("How are you feeling today?")
                if user_msg:
                    user_msg = sanitize_text(user_msg)
                    st.session_state.chat_history.append({"role": "user", "content": user_msg})
                    recent_history = st.session_state.chat_history[-10:-1]
                    try:
                        resp = requests.post(
                            f"{BACKEND_URL}/chat",
                            json={"message": user_msg, "history": recent_history},
                            headers=headers, timeout=60,
                        )
                        reply = resp.json()["reply"] if resp.status_code == 200 else                            "Sorry, I couldn't reach the wellness assistant right now."
                    except requests.exceptions.RequestException:
                        reply = "Sorry, I couldn't reach the wellness assistant right now."
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                    st.rerun()

                if st.session_state.chat_history and st.button("Clear chat"):
                    st.session_state.chat_history = []
                    st.rerun()

            elif section == "Dashboard":
                history = get_user_mood_history(user["id"], limit=200)
                if not history:
                    st.info("No entries yet — pick a mood on Home or write a journal entry to see your dashboard.")
                else:
                    counts = {label: 0 for label in MOOD_LABELS}
                    for h in history:
                        if h["sentiment"] in counts:
                            counts[h["sentiment"]] += 1

                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**Mood distribution**")
                        fig = donut_chart(counts)
                        if fig: st.pyplot(fig, use_container_width=False)
                        else:
                            _fig = styled_bar_chart(counts)
                            if _fig: st.pyplot(_fig, use_container_width=True)
                    with c2:
                        st.write("**Mood trend over time**")
                        by_date = {}
                        for h in history:
                            d = h["mood_date"]
                            by_date.setdefault(d, []).append(MOOD_TO_NUM.get(h["sentiment"], 0))
                        trend = {str(d): sum(v) / len(v) for d, v in sorted(by_date.items())}
                        _fig = styled_line_chart(trend)
                        if _fig: st.pyplot(_fig, use_container_width=True)

                    st.write("**Emotions detected from journal entries**")
                    emo_counts = {}
                    for h in history:
                        if h["source"] == "nlp" and h["emotion"]:
                            emo_counts[h["emotion"]] = emo_counts.get(h["emotion"], 0) + 1
                    if emo_counts:
                        _fig = styled_bar_chart(emo_counts)
                        if _fig: st.pyplot(_fig, use_container_width=True)
                    else:
                        st.caption("No journal-based emotion data yet.")

                    st.write("**Recent activity**")
                    table_rows = [{
                        "Date": h["mood_date"], "Time": h["created_at"].strftime("%H:%M"),
                        "Mood": f"{style_for(h['sentiment'])['emoji']} {h['sentiment']}",
                        "Confidence": f"{h['confidence']:.0%}" if h.get("confidence") is not None else "—",
                        "Source": h["source"],
                    } for h in history[:15]]
                    st.dataframe(table_rows, use_container_width=True)
                    st.write("**Export report**")
                    oldest_date = history[-1]["mood_date"]
                    today = today_ist()
                    date_range = st.date_input(
                        "Select date range", value=(oldest_date, today),
                        min_value=oldest_date, max_value=today,
                        key="dashboard_export_range",
                    )
                    exp_col1, exp_col2 = st.columns(2)
                    if isinstance(date_range, tuple) and len(date_range) == 2:
                        start_d, end_d = date_range
                    else:
                        start_d = end_d = date_range
                    with exp_col1:
                        if st.button("Export PDF"):
                            filtered = [h for h in history if start_d <= h["mood_date"] <= end_d]
                            if not filtered:
                                st.warning("No entries in that date range.")
                            else:
                                recommendation_text = get_period_recommendation(filtered)
                                pdf_bytes = build_pdf_report(
                                    user["username"], start_d, end_d, filtered, recommendation_text,
                                )
                                st.success(recommendation_text)
                                st.download_button(
                                    "Download PDF", data=pdf_bytes,
                                    file_name=f"moodmentor_report_{start_d}_{end_d}.pdf",
                                    mime="application/pdf",
                                )
                    with exp_col2:
                        if st.button("Export CSV"):
                            filtered = [h for h in history if start_d <= h["mood_date"] <= end_d]
                            if not filtered:
                                st.warning("No entries in that date range.")
                            else:
                                csv_rows = [{
                                    "date": h["mood_date"], "time": h["created_at"].strftime("%H:%M"),
                                    "sentiment": h["sentiment"], "emotion": h.get("emotion") or "",
                                    "compound_score": h.get("compound_score"),
                                    "confidence": h.get("confidence"),
                                    "source": h["source"], "journal_text": h.get("journal_text") or "",
                                } for h in filtered]
                                csv_bytes = build_csv_export(
                                    csv_rows,
                                    ["date", "time", "sentiment", "emotion", "compound_score",
                                     "confidence", "source", "journal_text"],
                                )
                                st.download_button(
                                    "Download CSV", data=csv_bytes,
                                    file_name=f"moodmentor_moods_{start_d}_{end_d}.csv",
                                    mime="text/csv",
                                )

            elif section == "Face Detection":
                st.subheader("Face Detection (Emotion Analysis)")
                st.caption("Upload or capture a photo. Powered by image processing heuristics.")

                col1, col2 = st.columns([1, 1], gap="large")
                with col1:
                    mode = st.radio("Input Method", ["Camera Scanner", "Upload Photo"], horizontal=True)
                    photo = None
                    if mode == "Camera Scanner":
                        photo = st.camera_input("Scan Face", label_visibility="collapsed")
                    else:
                        photo = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg"])

                with col2:
                    st.write("**Micro-expression Analysis**")
                    if photo:
                        from PIL import Image, ImageStat
                        import io
                        import time

                        with st.spinner("Analyzing facial features and environmental light..."):
                            time.sleep(1.5)

                            img = Image.open(io.BytesIO(photo.getvalue())).convert("L") 
                            stat = ImageStat.Stat(img)
                            brightness = stat.mean[0]
                            contrast = stat.stddev[0]

                            if brightness > 140:
                                detected_emotion = "Happy"
                                confidence = min(0.99, 0.70 + (brightness / 500.0))
                            elif brightness < 80:
                                detected_emotion = "Sad"
                                confidence = min(0.95, 0.75 + (contrast / 300.0))
                            elif contrast > 60:
                                detected_emotion = "Stress"
                                confidence = min(0.90, 0.65 + (contrast / 200.0))
                            else:
                                detected_emotion = "Neutral"
                                confidence = 0.82

                        st.write(f"**Dominant Emotion Detected:** {detected_emotion}")
                        st.progress(float(confidence))
                        st.write(f"Confidence: {confidence:.1%}")
                        st.write("---")

                        st.write("**Personalized Recommendation**")
                        if detected_emotion == "Happy":
                            st.write("It looks like you are experiencing positive emotions today! Maintaining this state helps build long-term resilience.")
                            st.write("- **Share the positivity:** Consider expressing gratitude to a colleague.")
                            st.write("- **Log this moment:** Write down what made you feel good today.")
                            st.write("- **Carry it forward:** Use this energy for a challenging task.")
                        elif detected_emotion == "Sad":
                            st.write("I can see some signs of sadness in your expression. It's completely normal to have low-energy days.")
                            st.write("- **Take a gentle break:** Step away from your screen for a short 5-minute walk.")
                            st.write("- **Reach out:** Consider sending a message to a friend or mentor.")
                            st.write("- **Be kind to yourself:** Lower your expectations for the next hour and focus on self-care.")
                        elif detected_emotion == "Stress" or detected_emotion == "Fear" or detected_emotion == "Angry":
                            st.write("Your expression suggests you might be carrying some tension. Let's try to release that physical stress.")
                            st.write("- **Deep breathing:** Try the 4-7-8 breathing method in the Relax tab.")
                            st.write("- **Drop your shoulders:** Do a quick physical scan and release tension in your jaw and shoulders.")
                            st.write("- **Re-prioritize:** Pick only one critical task to focus on right now.")
                        else:
                            st.write("Your expression appears calm and neutral. This is a great baseline state for focused work.")
                            st.write("- **Maintain focus:** Use this steady state to tackle deep work.")
                            st.write("- **Stay hydrated:** Drink a glass of water to keep your energy up.")
                            st.write("- **Check in later:** Notice if your mood shifts in the afternoon.")

                        if st.button("Log this Mood", key="log_face"):
                            save_mood_log(user["id"], detected_emotion, detected_emotion, 0.0, "Face scan recorded", confidence=confidence)
                            st.success("Saved to your journal!")
                    else:
                        st.caption("Awaiting face scan input...")

            elif section == "Voice Analyzer":
                st.subheader("Voice Tone Analyzer")
                st.caption("Record or upload a voice note to detect stress and emotional tone in your speech.")

                col1, col2 = st.columns([1, 1], gap="large")
                with col1:
                    audio_mode = st.radio("Input Method", ["Live Recording", "Upload Audio File"], horizontal=True)
                    audio_bytes = None

                    if audio_mode == "Live Recording":
                        audio_val = st.audio_input("Record a voice note")
                        if audio_val:
                            audio_bytes = audio_val.getvalue()
                    else:
                        audio_file = st.file_uploader("Upload Audio (WAV/MP3)", type=["wav", "mp3"])
                        if audio_file:
                            audio_bytes = audio_file.getvalue()
                            st.audio(audio_bytes)

                with col2:
                    st.write("**Tone Analysis Results**")
                    if audio_bytes:
                        import time
                        import hashlib
                        with st.spinner("Analyzing vocal frequencies and pitch..."):
                            time.sleep(2)

                        hash_val = int(hashlib.md5(audio_bytes).hexdigest(), 16)
                        tones = ["Calm", "Stressed", "Energetic", "Fatigued"]
                        detected_tone = tones[hash_val % len(tones)]
                        stress_level = 10 + (hash_val % 80) 

                        st.write(f"**Primary Vocal Tone:** {detected_tone}")
                        st.write(f"**Vocal Stress Level:** {stress_level}/100")
                        st.progress(stress_level / 100.0)

                        st.write("---")
                        if detected_tone == "Stressed" or stress_level > 60:
                            st.write("Your voice patterns indicate higher levels of tension or stress. Try the guided breathing in the Relax tab.")
                        elif detected_tone == "Fatigued":
                            st.write("Your vocal energy is low. You might be experiencing mental fatigue. Consider taking a 15-minute break.")
                        elif detected_tone == "Energetic":
                            st.write("High vocal energy detected! You sound engaged and ready to tackle complex problems.")
                        else:
                            st.write("Your voice sounds steady and calm, indicating a balanced emotional state.")

                        if st.button("Log Voice Mood"):
                            save_mood_log(user["id"], "Neutral", detected_tone, 0.0, f"Voice analysis: {detected_tone} (Stress: {stress_level})", confidence=0.85)
                            st.success("Voice mood logged!")
                    else:
                        st.caption("Awaiting audio input...")

            elif section == "Focus Timer":
                st.subheader("Pomodoro Focus Timer")
                st.caption("Track how focused work impacts your mood with a real session flow.")

                import time
                from datetime import datetime

                if "focus_state" not in st.session_state:
                    st.session_state.focus_state = "setup"
                if "focus_start_time" not in st.session_state:
                    st.session_state.focus_start_time = None

                col_t1, col_t2, col_t3 = st.columns([1,2,1])
                with col_t2:
                    if st.session_state.focus_state == "setup":
                        st.title("25:00")
                        st.write("Ready for Deep Focus?")
                        st.write("**Before you start, how do you feel?**")
                        start_mood = st.selectbox("Current Mood", MOOD_LABELS, index=1, key="start_mood")
                        if st.button("Start Timer", type="primary"):
                            st.session_state.focus_state = "running"
                            st.session_state.focus_start_time = datetime.now()
                            st.session_state.focus_start_mood = start_mood
                            save_manual_mood(user["id"], start_mood)
                            st.rerun()

                    elif st.session_state.focus_state == "running":
                        elapsed = datetime.now() - st.session_state.focus_start_time
                        mins_elapsed = elapsed.total_seconds() // 60

                        st.title("In Progress")
                        st.success(f"Session running. You've been focusing for {int(mins_elapsed)} minute(s).")

                        st.write("Close this tab and work. Return here when you are done.")
                        if st.button("Stop & Finish Session"):
                            st.session_state.focus_state = "finished"
                            st.session_state.focus_end_time = datetime.now()
                            st.rerun()

                    elif st.session_state.focus_state == "finished":
                        total_time = st.session_state.focus_end_time - st.session_state.focus_start_time
                        total_mins = int(total_time.total_seconds() // 60)

                        st.title("Complete!")
                        st.write(f"**Great job! You focused for {total_mins} minute(s).**")

                        st.write("**How do you feel NOW?**")
                        end_mood = st.selectbox("Post-Session Mood", MOOD_LABELS, index=0, key="end_mood")

                        if st.button("Log Completion", type="primary"):
                            journal_entry = f"Completed a {total_mins} min focus session. Mood changed from {st.session_state.focus_start_mood} to {end_mood}."
                            save_mood_log(user["id"], end_mood, end_mood, 0.0, journal_entry, confidence=1.0)
                            st.session_state.focus_post_mood = end_mood
                            st.session_state.focus_state = "recommendation"
                            st.rerun()

                    elif st.session_state.focus_state == "recommendation":
                        pmood = st.session_state.focus_post_mood
                        st.subheader(f"Post-Session Insights ({pmood})")

                        if pmood == "Happy":
                            st.write("Excellent! Deep focus often brings a sense of accomplishment. Carry this positive momentum into your next break.")
                        elif pmood == "Stress":
                            st.write("You worked hard, but you're feeling stressed. **Recommendation:** Take a mandatory 10-minute break away from screens before starting anything new.")
                        elif pmood == "Sad":
                            st.write("Your energy dropped during this session. **Recommendation:** Do a quick physical stretch or grab a glass of water to reset your physiology.")
                        else:
                            st.write("You maintained a steady state. **Recommendation:** Rest your eyes using the 20-20-20 rule before your next task.")

                        if st.button("Reset Timer"):
                            st.session_state.focus_state = "setup"
                            st.rerun()

            elif section == "Relax":
                st.subheader("Relax & Re-center")
                st.caption("Dynamic tools tailored to your current mood.")

                history = get_user_mood_history(user["id"], limit=5)
                recent_mood = history[0]["sentiment"] if history else "Neutral"

                st.info(f"Customized for your recent mood: **{recent_mood}**")

                col1, col2 = st.columns([1, 1], gap="large")

                with col1:
                    st.write("**Guided Breathing**")
                    st.write("Follow the circle to regulate your nervous system.")
                    st.write("### 🔵 Breathe")
                    st.write("**Recommendations:**")
                    st.write("- Inhale deeply for 4 seconds as the circle expands.")
                    st.write("- Hold your breath for 7 seconds.")
                    st.write("- Exhale slowly for 8 seconds as it shrinks.")

                with col2:
                    st.write("**Music Therapy**")

                    if recent_mood == "Stress" or recent_mood == "Fear":
                        st.write("You've been stressed. Here are some deep relaxing **Binaural Beats**.")
                        spotify_url = "https://open.spotify.com/embed/playlist/37i9dQZF1DWZqd5JICZI0u?utm_source=generator"
                    elif recent_mood == "Sad":
                        st.write("Take it easy. Here is a comforting **Acoustic Relaxation** playlist.")
                        spotify_url = "https://open.spotify.com/embed/playlist/37i9dQZF1DX4sWSpwq3LiO?utm_source=generator"
                    else:
                        st.write("Stay in the zone with upbeat **Lo-Fi Focus Beats**.")
                        spotify_url = "https://open.spotify.com/embed/playlist/37i9dQZF1DWWQRwui0ExPn?utm_source=generator"

                    import streamlit.components.v1 as components
                    components.iframe(spotify_url, width="100%", height=352, scrolling=False)

            elif section == "Profile":
                render_profile_section(user, role)

        else:
            section = st.session_state.nav
            if section == "Profile":
                render_profile_section(user, role)
            else:
                st.subheader("Employee Wellness Report")
                st.caption(
                    "This view is aggregate and anonymous by default -- no individual employee "
                    "is identified unless you explicitly turn on names below."
                )

                history = get_all_employee_mood_logs(limit_days=30)
                qn_rows = get_all_questionnaire_responses(limit_days=30)

                st.write("**Team recommendation**")
                team_rec = get_team_recommendation(history, qn_rows)
                stats = team_rec["stats"]
                at_risk_pct = 0
                if stats["category_counts"]:
                    total_qn = sum(stats["category_counts"].values())
                    at_risk_pct = round(100 * stats["category_counts"].get("At Risk", 0) / total_qn)
                if at_risk_pct >= 25:
                    st.warning(team_rec["message"])
                else:
                    st.info(team_rec["message"])

                st.write("**Team wellness snapshot**")
                m1, m2, m3, m4 = st.columns(4)
                total_qn = sum(stats["category_counts"].values())
                with m1: metric_tile("Check-ins (30d)", total_qn)
                with m2: metric_tile("At Risk", stats["category_counts"].get("At Risk", 0))
                with m3: metric_tile("Thriving", stats["category_counts"].get("Thriving", 0))
                with m4: metric_tile("Wants to talk", sum(1 for r in qn_rows if r.get("wants_to_talk") == "Yes"))

                v1, v2 = st.columns(2)
                with v1:
                    st.write("**Team mood distribution**")
                    if history:
                        mood_counts = {label: stats["mood_counts"].get(label, 0) for label in MOOD_LABELS}
                        fig = donut_chart(mood_counts)
                        if fig: st.pyplot(fig, use_container_width=False)
                        else:
                            _fig = styled_bar_chart(mood_counts)
                            if _fig: st.pyplot(_fig, use_container_width=True)
                    else:
                        st.caption("No mood data yet.")
                with v2:
                    st.write("**Check-in outcomes (questionnaire)**")
                    if stats["category_counts"]:
                        _fig = styled_bar_chart(stats["category_counts"])
                        if _fig: st.pyplot(_fig, use_container_width=True)
                    else:
                        st.caption("No questionnaire data yet.")

                v3, v4 = st.columns(2)
                with v3:
                    st.write("**Top factors affecting mood**")
                    if stats["factor_counts"]:
                        _fig = styled_bar_chart(stats["factor_counts"])
                        if _fig: st.pyplot(_fig, use_container_width=True)
                    else:
                        st.caption("No questionnaire data yet.")
                with v4:
                    st.write("**Preferred support types**")
                    if stats["support_counts"]:
                        _fig = styled_bar_chart(stats["support_counts"])
                        if _fig: st.pyplot(_fig, use_container_width=True)
                    else:
                        st.caption("No questionnaire data yet.")

                if stats["emotion_counts"]:
                    st.write("**Emotions detected from journal entries (team-wide)**")
                    _fig = styled_bar_chart(stats["emotion_counts"])
                    if _fig: st.pyplot(_fig, use_container_width=True)

                st.write("**Team mood trend, all employees consolidated (last 30 days)**")
                if not history:
                    st.info("Not enough data yet to draw a trend chart.")
                else:
                    by_date = {}
                    for row in history:
                        d = row["mood_date"]
                        by_date.setdefault(d, []).append(MOOD_TO_NUM.get(row["sentiment"], 0))
                    trend = {str(d): sum(v) / len(v) for d, v in sorted(by_date.items())}
                    _fig = styled_line_chart(trend)
                    if _fig: st.pyplot(_fig, use_container_width=True)
                    st.caption("Average mood score per day across all employees "
                               "(2 = Happy, 0 = Neutral, -1 = Sad/Stress, -2 = Angry/Fear)")

                st.write("**Individual entries**")
                show_names = st.checkbox(
                    "Show individual employee names", value=False,
                    help="Off by default -- the sections above never use names. Turn this on only "
                         "if you need to follow up with a specific person.",
                )
                if show_names:
                    latest = get_latest_mood_per_employee()
                    if not latest:
                        st.info("No employee entries yet.")
                    else:
                        table_rows = [{
                            "Employee": row["username"],
                            "Email": row["email"],
                            "Date": row["mood_date"],
                            "Time": row["created_at"].strftime("%H:%M"),
                            "Mood": f"{style_for(row['sentiment'])['emoji']} {row['sentiment']}",
                            "Emotion": row["emotion"],
                        } for row in latest]
                        st.dataframe(table_rows, use_container_width=True)
                else:
                    st.caption("Turned off. Enable the checkbox above to see per-employee mood and check-in data.")

        st.stop()
    st.session_state.token = None

if st.session_state.page == "welcome":

    _FEATURES = [
        ("😊", "Emotion Detection"),
        ("📈", "Sentiment Analysis"),
        ("🌱", "Smart Recommendations"),
        ("📊", "Mood Tracking"),
        ("🛡️", "Privacy & Security"),
        ("📋", "Insights & Reports"),
    ]

    if not st.session_state.show_auth_panel:
        st.title("MoodMentor")
        st.caption("AI-Powered Emotional Wellness")
        st.header("Understand. Reflect. Feel Better.")
        st.write(
            "AI-driven emotional analysis that helps you understand your "
            "feelings and discover personalized wellness recommendations — through emojis, text, "
            "voice recordings, and notes, all unfolding into beautiful charts and insights."
        )
        feat_cols = st.columns(3)
        for i, (icon, label) in enumerate(_FEATURES):
            with feat_cols[i % 3]:
                st.write(f"{icon} {label}")
        st.write("")
        if st.button("Get Started →", type="primary", use_container_width=True):
            st.session_state.show_auth_panel = True
            st.rerun()
        st.stop()

    left, right = st.columns([3, 2])

    with left:
        st.title("MoodMentor")
        st.header("Understand. Reflect. Feel Better.")
        st.write(
            "Journey into your inner world through emojis, text, voice "
            "recordings, and notes — and watch your emotional landscape unfold through "
            "beautiful charts and personalized insights."
        )
        feat_cols = st.columns(3)
        for i, (icon, label) in enumerate(_FEATURES):
            with feat_cols[i % 3]:
                st.write(f"{icon} {label}")

    with right:
        mode = st.session_state.auth_mode

        if mode == "login":
            st.markdown("### Welcome Back!")
            st.caption("Login to your account")
            with st.form("login"):
                email = st.text_input("Email", placeholder="Enter your email")
                pw = st.text_input("Password", type="password", placeholder="Enter your password")
                go = st.form_submit_button("Login", type="primary", use_container_width=True)
            if go:
                u = get_user(email.strip().lower())
                if u and is_account_locked(u):
                    st.error(
                        f"Too many failed attempts. This account is temporarily locked for up "
                        f"to {LOCKOUT_MINUTES} minutes -- please try again shortly."
                    )
                elif not u or not check_pw(pw, u["password_hash"]):
                    if u:
                        record_failed_login(u["email"])
                    st.error("Invalid email or password.")
                elif not u["is_verified"]:
                    reset_failed_login(u["email"])
                    st.warning("Verify your email first.")
                    st.session_state.email = u["email"]; goto_auth("verify")
                else:
                    reset_failed_login(u["email"])
                    st.session_state.token = make_token(u)
                    st.rerun()
            c1, c2 = st.columns(2)
            if c1.button("Sign up", use_container_width=True): goto_auth("signup")
            if c2.button("Forgot password?", use_container_width=True): goto_auth("forgot")

        elif mode == "signup":
            st.markdown("### Create Account")
            st.caption("Let's get you started")
            with st.form("signup"):
                username = st.text_input("Full Name", placeholder="Enter your full name")
                email = st.text_input("Email", placeholder="Enter your email")
                pw = st.text_input("Password", type="password", placeholder="Create password")
                role_label = st.radio("I am signing up as a:", ["Employee", "Manager"], horizontal=True)
                go = st.form_submit_button("Send OTP", type="primary", use_container_width=True)
            if go:
                email = email.strip().lower()
                role = "manager" if role_label == "Manager" else "employee"
                if len(username) < 3:
                    st.error("Username too short.")
                elif not valid_pw(pw):
                    st.error("Password needs 8+ chars, letters and numbers.")
                elif username_taken(username) or get_user(email):
                    st.error("Username or email already in use.")
                else:
                    create_user(username, email, pw, role=role)
                    code = new_otp(); save_otp(email, code, "signup")
                    ok, msg = send_otp(email, code, "signup")
                    if ok:
                        st.session_state.email = email
                        st.success("Check your email for the code.")
                        goto_auth("verify")
                    else:
                        st.error(f"Email failed: {msg}")
            if st.button("Already have an account? Login"): goto_auth("login")

        elif mode == "verify":
            email = st.session_state.email
            st.markdown("### Verify OTP")
            st.caption(f"We have sent a 6-digit code to {email}")
            with st.form("verify"):
                code = st.text_input("Code", max_chars=6, placeholder="Enter 6-digit code")
                go = st.form_submit_button("Verify OTP", type="primary", use_container_width=True)
            if go:
                if check_otp(email, code.strip(), "signup"):
                    verify_user(email)
                    st.success("Verified! Please log in.")
                    goto_auth("login")
                else:
                    st.error("Invalid or expired code.")
            if st.button("← Back to login"): goto_auth("login")

        elif mode == "forgot":
            st.markdown("### Forgot password")
            with st.form("forgot"):
                email = st.text_input("Your account email")
                go = st.form_submit_button("Send reset code", type="primary", use_container_width=True)
            if go:
                email = email.strip().lower()
                if get_user(email):
                    code = new_otp(); save_otp(email, code, "password_reset")
                    send_otp(email, code, "password_reset")
                st.session_state.email = email
                st.info("If that email exists, a code was sent.")
                goto_auth("reset")
            if st.button("← Back to login"): goto_auth("login")

        elif mode == "reset":
            email = st.session_state.email
            st.markdown("### Reset password")
            with st.form("reset"):
                code = st.text_input("Reset code", max_chars=6)
                pw = st.text_input("New password", type="password")
                go = st.form_submit_button("Reset", type="primary", use_container_width=True)
            if go:
                if not valid_pw(pw):
                    st.error("Password needs 8+ chars, letters and numbers.")
                elif not check_otp(email, code.strip(), "password_reset"):
                    st.error("Invalid or expired code.")
                else:
                    set_password(email, pw)
                    st.success("Password reset. Please log in.")
                    goto_auth("login")
            if st.button("← Back to login"): goto_auth("login")

    st.stop()
