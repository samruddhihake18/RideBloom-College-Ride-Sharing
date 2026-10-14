import streamlit as st
import sqlite3, hashlib, secrets, math
from datetime import datetime, date, time, timedelta
from pathlib import Path
import pandas as pd
import folium
from streamlit_folium import st_folium

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "ridebloom.db"
st.set_page_config(page_title="RideBloom | Campus Carpool", page_icon="🌼", layout="wide", initial_sidebar_state="expanded")

# ---------- Visual system ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root { --ink:#21352f; --muted:#718078; --green:#36765e; --mint:#eaf5ed; --peach:#fff0e5; --yellow:#f7d77b; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background:linear-gradient(140deg,#fbfcf7 0%,#f1f8f1 48%,#fff8ef 100%); color:var(--ink); }
h1,h2,h3 { font-family:'Manrope',sans-serif!important; color:#203b30; letter-spacing:-.035em; }
.block-container { padding-top:1.6rem; padding-bottom:3rem; max-width:1450px; }
[data-testid="stSidebar"] { background:#edf5ec; border-right:1px solid #dce9dc; }
[data-testid="stSidebar"] * { color:#244436; }
div.stButton > button { border-radius:14px; border:0; background:#34765c; color:white; font-weight:700; padding:.62rem 1rem; transition:.2s; }
div.stButton > button:hover { background:#245b45; color:white; transform:translateY(-1px); }
div[data-testid="stFormSubmitButton"] button { border-radius:14px; background:#34765c; color:white; border:0; font-weight:700; }
div[data-testid="stMetric"] { background:rgba(255,255,255,.82); padding:18px 20px; border:1px solid #e2ebe0; border-radius:20px; box-shadow:0 5px 18px #29442a0a; }
div[data-testid="stMetricLabel"] { color:#718078; }
div[data-testid="stMetricValue"] { color:#2c674e; font-family:'Manrope',sans-serif; }
div[data-testid="stTabs"] button { border-radius:12px 12px 0 0; font-weight:700; }
.rb-hero { background:linear-gradient(115deg,#e1f2e3 0%,#f7f5df 58%,#ffe9d8 100%); border:1px solid #e0ebd8; padding:30px 34px; border-radius:28px; margin-bottom:20px; }
.rb-kicker { text-transform:uppercase; letter-spacing:.15em; color:#568269; font-weight:800; font-size:12px; }
.rb-title { font-family:'Manrope',sans-serif; font-size:42px; line-height:1.08; font-weight:800; color:#214a37; margin:8px 0 10px; }
.rb-sub { color:#5e7468; font-size:16px; max-width:760px; }
.rb-chip { display:inline-block; background:white; border:1px solid #dce9dc; border-radius:999px; padding:7px 12px; margin:4px 6px 0 0; color:#416c54; font-size:12px; font-weight:700; }
.rb-card { background:rgba(255,255,255,.88); border:1px solid #e3ece0; border-radius:22px; padding:20px; margin-bottom:12px; box-shadow:0 7px 20px #243f2908; }
.rb-card-title { color:#244b38; font-weight:800; font-size:18px; }
.rb-muted { color:#748078; font-size:13px; }
.rb-price { color:#2c7454; font-size:24px; font-weight:800; font-family:'Manrope',sans-serif; }
.rb-footer { color:#7b8980; font-size:12px; text-align:center; padding:18px; }
</style>
""", unsafe_allow_html=True)

# ---------- Database ----------
def connect():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
          student_id TEXT UNIQUE NOT NULL, department TEXT NOT NULL, year TEXT NOT NULL,
          phone TEXT, password_hash TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rides(
          id INTEGER PRIMARY KEY AUTOINCREMENT, driver_id INTEGER NOT NULL, from_place TEXT NOT NULL,
          to_place TEXT NOT NULL, ride_date TEXT NOT NULL, ride_time TEXT NOT NULL, seats_total INTEGER NOT NULL,
          seats_available INTEGER NOT NULL, vehicle TEXT, fare REAL NOT NULL DEFAULT 0, notes TEXT,
          from_lat REAL, from_lon REAL, to_lat REAL, to_lon REAL, status TEXT NOT NULL DEFAULT 'Open',
          created_at TEXT NOT NULL, FOREIGN KEY(driver_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS bookings(
          id INTEGER PRIMARY KEY AUTOINCREMENT, ride_id INTEGER NOT NULL, passenger_id INTEGER NOT NULL,
          seats INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'Confirmed',
          created_at TEXT NOT NULL, UNIQUE(ride_id,passenger_id),
          FOREIGN KEY(ride_id) REFERENCES rides(id), FOREIGN KEY(passenger_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS reviews(
          id INTEGER PRIMARY KEY AUTOINCREMENT, ride_id INTEGER NOT NULL, reviewer_id INTEGER NOT NULL,
          target_id INTEGER NOT NULL, rating INTEGER NOT NULL, comment TEXT, created_at TEXT NOT NULL,
          UNIQUE(ride_id,reviewer_id,target_id)
        );
        CREATE TABLE IF NOT EXISTS notifications(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, message TEXT NOT NULL,
          seen INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        # Safe demo content for first-run exploration.
        count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            demo_hash = password_hash("Bloom@123")
            c.execute("INSERT INTO users(name,email,student_id,department,year,phone,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?)",
                      ("Aarav Patil","aarav.demo@ridebloom.local","RB-DEMO-01","AI & DS","Final Year","9000000001",demo_hash,now()))
            uid = c.execute("SELECT id FROM users WHERE email=?",("aarav.demo@ridebloom.local",)).fetchone()[0]
            c.execute("""INSERT INTO rides(driver_id,from_place,to_place,ride_date,ride_time,seats_total,seats_available,vehicle,fare,notes,from_lat,from_lon,to_lat,to_lon,status,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (uid,"ADCET Main Gate","Sangli Railway Station",(date.today()+timedelta(days=1)).isoformat(),"08:15",3,3,"White Swift • MH 10",35,"Pickup near the main gate. Please be on time.",16.9504,74.4092,16.8524,74.5815,"Open",now()))
            c.execute("""INSERT INTO rides(driver_id,from_place,to_place,ride_date,ride_time,seats_total,seats_available,vehicle,fare,notes,from_lat,from_lon,to_lat,to_lon,status,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (uid,"Ashta Bus Stand","ADCET Main Gate",(date.today()+timedelta(days=2)).isoformat(),"08:30",2,2,"Honda Activa • MH 10",10,"Short campus commute.",16.9490,74.4098,16.9504,74.4092,"Open",now()))

def now(): return datetime.now().isoformat(timespec="seconds")
def password_hash(pw): return hashlib.sha256(("ridebloom-v1:"+pw).encode()).hexdigest()
def query(sql, params=()):
    with connect() as c: return c.execute(sql, params).fetchall()
def execute(sql, params=()):
    with connect() as c:
        cur = c.execute(sql, params)
        return cur.lastrowid
def notify(user_id, message):
    execute("INSERT INTO notifications(user_id,message,created_at) VALUES(?,?,?)",(user_id,message,now()))
def user_by_email(email):
    rows=query("SELECT * FROM users WHERE lower(email)=lower(?)",(email.strip(),))
    return rows[0] if rows else None
def get_user(uid):
    rows=query("SELECT * FROM users WHERE id=?",(uid,))
    return rows[0] if rows else None
def nice_date(d):
    try: return datetime.strptime(d,"%Y-%m-%d").strftime("%a, %d %b %Y")
    except: return d
def money(x): return "₹0" if float(x or 0)==0 else f"₹{float(x):.0f}"
def safe(s): return str(s or "").replace("<","&lt;").replace(">","&gt;")

init_db()

# ---------- Session / helpers ----------
if "user_id" not in st.session_state: st.session_state.user_id = None
if "page" not in st.session_state: st.session_state.page = "Explore rides"
if "map_pick" not in st.session_state: st.session_state.map_pick = "Pickup"
if "flash" not in st.session_state: st.session_state.flash = None

def set_page(p): st.session_state.page=p
def current_user(): return get_user(st.session_state.user_id) if st.session_state.user_id else None

def hero(kicker, title, subtitle, chips=None):
    chip_html = "".join(f'<span class="rb-chip">{x}</span>' for x in (chips or []))
    st.markdown(f'<div class="rb-hero"><div class="rb-kicker">{kicker}</div><div class="rb-title">{title}</div><div class="rb-sub">{subtitle}</div><div style="margin-top:12px">{chip_html}</div></div>',unsafe_allow_html=True)

def add_map(lat=16.9504, lon=74.4092, zoom=12, height=330, markers=None, click_key=None):
    m=folium.Map(location=[lat,lon],zoom_start=zoom,tiles="OpenStreetMap",control_scale=True)
    for item in (markers or []):
        folium.Marker([item["lat"],item["lon"]],tooltip=item["label"],popup=item["label"],
                      icon=folium.Icon(color=item.get("color","green"),icon=item.get("icon","map-marker"))).add_to(m)
    return st_folium(m,height=height,width=None,key=click_key,returned_objects=["last_clicked"] if click_key else [])

def add_notification(uid, msg): notify(uid,msg)

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 🌼 RideBloom")
    st.caption("Campus rides, shared simply.")
    st.divider()
    user=current_user()
    if user:
        st.markdown(f"**Hey, {safe(user['name'].split()[0])}!** 👋")
        st.caption(f"{safe(user['department'])} · {safe(user['year'])}")
        st.divider()
        pages=["Overview","Explore rides","Offer a ride","My bookings","My rides","Notifications","Safety & help","Profile"]
        for p in pages:
            icon={"Overview":"🏡","Explore rides":"🧭","Offer a ride":"🚗","My bookings":"🎟️","My rides":"🛣️","Notifications":"🔔","Safety & help":"🛟","Profile":"🌱"}.get(p,"•")
            if st.button(f"{icon}  {p}",key="nav_"+p,use_container_width=True):
                set_page(p); st.rerun()
        st.divider()
        if st.button("Log out",use_container_width=True):
            st.session_state.user_id=None; st.session_state.page="Explore rides"; st.rerun()
    else:
        st.markdown("### Welcome aboard")
        st.write("Sign in to book a seat or offer a ride.")
        if st.button("Sign in / Register",use_container_width=True):
            set_page("Sign in"); st.rerun()
        st.divider()
        if st.button("Explore demo rides",use_container_width=True):
            set_page("Explore rides"); st.rerun()
    st.markdown('<div class="rb-footer">Built for student communities</div>',unsafe_allow_html=True)

if st.session_state.flash:
    st.toast(st.session_state.flash)
    st.session_state.flash=None

# ---------- Auth ----------
def auth_page():
    hero("YOUR CAMPUS, CONNECTED","A better way to get there.","Find classmates heading your way, share the commute, and keep everyday travel a little lighter.",["🌿 Student-first","🤝 Shared costs"])
    tab1,tab2=st.tabs(["Sign in","Create student account"])
    with tab1:
        with st.form("login_form"):
            email=st.text_input("College or personal email",placeholder="you@example.com")
            pw=st.text_input("Password",type="password")
            submit=st.form_submit_button("Sign in →",use_container_width=True)
        if submit:
            u=user_by_email(email)
            if u and u["password_hash"]==password_hash(pw):
                st.session_state.user_id=u["id"]; st.session_state.page="Overview"; st.rerun()
            else: st.error("Email or password doesn't match. Try again.")
        st.info("Demo login: **aarav.demo@ridebloom.local** · password **Bloom@123**")
    with tab2:
        with st.form("register_form"):
            a,b=st.columns(2)
            name=a.text_input("Full name *")
            email=b.text_input("Email *")
            student_id=a.text_input("College ID / roll number *")
            phone=b.text_input("Phone (optional)")
            dept=a.selectbox("Department",["AI & DS","CSE","IT","ENTC","Mechanical","Civil","Other"])
            year=b.selectbox("Study year",["First Year","Second Year","Third Year","Final Year","Postgraduate"])
            p1=a.text_input("Create password *",type="password")
            p2=b.text_input("Confirm password *",type="password")
            agree=st.checkbox("I will use RideBloom respectfully and share accurate ride details.")
            submitted=st.form_submit_button("Create my account 🌼",use_container_width=True)
        if submitted:
            if not all([name.strip(),email.strip(),student_id.strip(),p1,p2]):
                st.error("Please complete all required fields.")
            elif "@" not in email or "." not in email.split("@")[-1]:
                st.error("Enter a valid email address.")
            elif len(p1)<8:
                st.error("Use a password with at least 8 characters.")
            elif p1!=p2: st.error("Passwords do not match.")
            elif not agree: st.error("Please accept the community guidelines.")
            elif user_by_email(email) or query("SELECT id FROM users WHERE lower(student_id)=lower(?)",(student_id.strip(),)):
                st.error("That email or college ID is already registered.")
            else:
                try:
                    uid=execute("INSERT INTO users(name,email,student_id,department,year,phone,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?)",
                                (name.strip(),email.strip(),student_id.strip(),dept,year,phone.strip(),password_hash(p1),now()))
                    st.session_state.user_id=uid; st.session_state.page="Overview"
                    st.session_state.flash="Welcome to RideBloom! Your account is ready."
                    st.rerun()
                except sqlite3.IntegrityError: st.error("Email or college ID already exists.")
    st.caption("Prototype note: account details are stored in the app database. Use a demo account for presentations; do not enter sensitive information.")

# ---------- Explore ----------
def explore_page():
    hero("LESS SOLO. MORE TOGETHER.","Find your next ride. 🌼","Search student rides by destination and date, compare available seats, and book in a couple of clicks.",["🗺️ OpenStreetMap","💚 Student community","💸 Transparent fare"])
    a,b,c=st.columns([2,1,1])
    with a: destination=st.text_input("Where are you going?",placeholder="e.g. Sangli, bus stand, college")
    with b: ride_day=st.date_input("Travel date",value=date.today(),min_value=date.today())
    with c: seats_need=st.selectbox("Seats needed",[1,2,3,4],index=0)
    allrides=query("""SELECT r.*,u.name driver_name,u.department driver_dept,
        (SELECT AVG(rating) FROM reviews WHERE target_id=u.id) driver_rating
        FROM rides r JOIN users u ON r.driver_id=u.id
        WHERE r.status='Open' AND r.seats_available>=? AND r.ride_date>=? ORDER BY r.ride_date,r.ride_time""",(seats_need,date.today().isoformat()))
    results=[]
    for r in allrides:
        hay=(r["from_place"]+" "+r["to_place"]+" "+(r["notes"] or "")).lower()
        if (not destination.strip() or destination.lower() in hay) and (not ride_day or r["ride_date"]==ride_day.isoformat()):
            results.append(r)
    x,y,z=st.columns(3)
    x.metric("Rides matching",len(results))
    y.metric("Seats available",sum(r["seats_available"] for r in results))
    z.metric("Map access","Free")
    st.markdown("### Rides for your route")
    if not results:
        st.info("No rides match these filters yet. Try another date or destination—or offer a ride so someone else can join.")
    for r in results:
        with st.container(border=True):
            l,mid,right=st.columns([3,2,1])
            with l:
                st.markdown(f"**{safe(r['from_place'])}**  →  **{safe(r['to_place'])}**")
                st.caption(f"🚗 {safe(r['vehicle'] or 'Vehicle not specified')} · Driver: {safe(r['driver_name'])}")
                st.caption(f"📅 {nice_date(r['ride_date'])} · 🕒 {r['ride_time']} · 👥 {r['seats_available']} seat(s) left")
                if r["notes"]: st.write(r["notes"])
            with mid:
                st.markdown(f'<div class="rb-price">{money(r["fare"])}</div><div class="rb-muted">suggested cost per seat</div>',unsafe_allow_html=True)
                if r["driver_rating"]: st.caption(f"⭐ {r['driver_rating']:.1f} driver rating")
                else: st.caption("New driver · no ratings yet")
            with right:
                uid=st.session_state.user_id
                if uid is None:
                    st.button("Sign in to book",key=f"signin_{r['id']}",on_click=set_page,args=("Sign in",))
                elif uid==r["driver_id"]:
                    st.caption("Your ride")
                else:
                    if st.button("Book seat",key=f"book_{r['id']}",use_container_width=True):
                        existing=query("SELECT id FROM bookings WHERE ride_id=? AND passenger_id=? AND status='Confirmed'",(r["id"],uid))
                        if existing: st.warning("You already booked this ride.")
                        elif r["seats_available"]<seats_need: st.error("Not enough seats remain.")
                        else:
                            try:
                                execute("INSERT INTO bookings(ride_id,passenger_id,seats,status,created_at) VALUES(?,?,?,?,?)",(r["id"],uid,seats_need,"Confirmed",now()))
                                execute("UPDATE rides SET seats_available=seats_available-? WHERE id=?",(seats_need,r["id"]))
                                notify(r["driver_id"],f"{current_user()['name']} booked {seats_need} seat(s) on your ride to {r['to_place']}.")
                                st.session_state.flash="Seat booked! Check My bookings for details."
                                st.rerun()
                            except sqlite3.IntegrityError: st.error("You already booked this ride.")
    st.markdown("### Free map preview")
    st.caption("Explore campus-area locations and common commute points.")
    add_map(markers=[{"lat":16.9504,"lon":74.4092,"label":"ADCET Main Gate"},{"lat":16.9490,"lon":74.4098,"label":"Ashta Bus Stand"},{"lat":16.8524,"lon":74.5815,"label":"Sangli Railway Station","color":"orange"}],click_key="explore_map")

# ---------- Offer ride ----------
def offer_page():
    hero("GOT A SPARE SEAT?","Turn your commute into a connection.","Post your route once. Classmates can find it, check the seats, and request a spot.",["🚗 Offer seats","💰 Set shared cost","🗺️ Pin pickup/drop-off"])
    u=current_user()
    if not u:
        st.warning("Sign in or create a student account before posting a ride.")
        if st.button("Go to sign in"): set_page("Sign in"); st.rerun()
        return
    st.markdown("### Ride details")
    with st.form("offer_ride_form"):
        c1,c2=st.columns(2)
        origin=c1.text_input("Pickup point *",placeholder="e.g. ADCET Main Gate")
        dest=c2.text_input("Destination *",placeholder="e.g. Sangli Railway Station")
        c3,c4,c5=st.columns(3)
        rd=c3.date_input("Travel date",value=date.today()+timedelta(days=1),min_value=date.today())
        rt=c4.time_input("Departure time",value=time(8,15),step=timedelta(minutes=15))
        seats=c5.selectbox("Seats to share",[1,2,3,4,5,6])
        c6,c7=st.columns(2)
        vehicle=c6.text_input("Vehicle / identifier",placeholder="e.g. Blue Activa · MH 10")
        fare=c7.number_input("Suggested cost per passenger (₹)",min_value=0,max_value=5000,value=20,step=5)
        notes=st.text_area("Extra details",placeholder="Pickup landmark, luggage, timing notes…",max_chars=300)
        st.markdown("**Optional map pins**")
        st.caption("Tap the map to set pickup and destination coordinates. If you skip this, the ride still works with text locations.")
        save=st.form_submit_button("Publish ride 🌿",use_container_width=True)
    # map selection outside form to keep map interactive
    if "pickup_pin" not in st.session_state: st.session_state.pickup_pin=None
    if "drop_pin" not in st.session_state: st.session_state.drop_pin=None
    mcol1,mcol2=st.columns([1,2])
    with mcol1:
        st.radio("Pin to set",["Pickup","Destination"],key="map_pick",horizontal=False)
        if st.button("Clear selected pin"):
            if st.session_state.map_pick=="Pickup": st.session_state.pickup_pin=None
            else: st.session_state.drop_pin=None
            st.rerun()
        if st.session_state.pickup_pin: st.success(f"Pickup pinned: {st.session_state.pickup_pin[0]:.4f}, {st.session_state.pickup_pin[1]:.4f}")
        if st.session_state.drop_pin: st.success(f"Destination pinned: {st.session_state.drop_pin[0]:.4f}, {st.session_state.drop_pin[1]:.4f}")
    with mcol2:
        mapres=add_map(height=300,zoom=12,markers=([{"lat":st.session_state.pickup_pin[0],"lon":st.session_state.pickup_pin[1],"label":"Pickup","color":"green"}] if st.session_state.pickup_pin else [])+([{"lat":st.session_state.drop_pin[0],"lon":st.session_state.drop_pin[1],"label":"Destination","color":"orange"}] if st.session_state.drop_pin else []),click_key="offer_pick_map")
        if mapres and mapres.get("last_clicked"):
            pt=mapres["last_clicked"]; coords=(float(pt["lat"]),float(pt["lng"]))
            key="pickup_pin" if st.session_state.map_pick=="Pickup" else "drop_pin"
            if st.session_state.get(key)!=coords:
                st.session_state[key]=coords; st.rerun()
    if save:
        if not origin.strip() or not dest.strip(): st.error("Pickup and destination are required.")
        elif origin.strip().lower()==dest.strip().lower(): st.error("Pickup and destination should be different.")
        elif rd<date.today(): st.error("Choose today or a future date.")
        else:
            p=st.session_state.pickup_pin; d=st.session_state.drop_pin
            execute("""INSERT INTO rides(driver_id,from_place,to_place,ride_date,ride_time,seats_total,seats_available,vehicle,fare,notes,from_lat,from_lon,to_lat,to_lon,status,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(u["id"],origin.strip(),dest.strip(),rd.isoformat(),rt.strftime("%H:%M"),seats,seats,vehicle.strip(),fare,notes.strip(),p[0] if p else None,p[1] if p else None,d[0] if d else None,d[1] if d else None,"Open",now()))
            st.session_state.flash="Your ride is live. Let the right people find it!"
            st.session_state.pickup_pin=None; st.session_state.drop_pin=None
            st.session_state.page="My rides"; st.rerun()

# ---------- Overview ----------
def overview_page():
    u=current_user()
    if not u: auth_page(); return
    hero("GOOD MORNING, COMMUTER 🌼",f"Welcome back, {safe(u['name'].split()[0])}.","Your next good commute could be one seat away.",["Small rides. Shared journeys.","Designed for campus life."])
    bookings=query("""SELECT b.*,r.from_place,r.to_place,r.ride_date,r.ride_time,r.fare,r.status ride_status,u.name driver_name
                      FROM bookings b JOIN rides r ON b.ride_id=r.id JOIN users u ON r.driver_id=u.id
                      WHERE b.passenger_id=? AND b.status='Confirmed' ORDER BY r.ride_date,r.ride_time""",(u["id"],))
    myrides=query("SELECT * FROM rides WHERE driver_id=? AND status='Open' ORDER BY ride_date,ride_time",(u["id"],))
    all_open=query("SELECT COUNT(*) n FROM rides WHERE status='Open' AND seats_available>0 AND ride_date>=?",(date.today().isoformat(),))[0]["n"]
    a,b,c,d=st.columns(4)
    a.metric("Open rides",all_open)
    b.metric("My bookings",len(bookings))
    c.metric("Rides I offer",len(myrides))
    d.metric("Unread alerts",query("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND seen=0",(u["id"],))[0]["n"])
    left,right=st.columns([1.3,1])
    with left:
        st.markdown("### Your upcoming rides")
        if not bookings: st.info("No bookings yet. Explore rides and grab a seat when a route fits.")
        for r in bookings[:3]:
            with st.container(border=True):
                st.markdown(f"**{safe(r['from_place'])}** → **{safe(r['to_place'])}**")
                st.caption(f"{nice_date(r['ride_date'])} · {r['ride_time']} · Driver: {safe(r['driver_name'])}")
                st.markdown(f"Shared cost: **{money(r['fare']*r['seats'])}** · {r['seats']} seat(s)")
    with right:
        st.markdown("### Your campus map")
        add_map(height=280,markers=[{"lat":16.9504,"lon":74.4092,"label":"ADCET Main Gate"},{"lat":16.9490,"lon":74.4098,"label":"Ashta Bus Stand"}],click_key="overview_map")
        st.markdown('<div class="rb-card"><div class="rb-card-title">🌱 Good commute habits</div><p class="rb-muted">Confirm pickup details, arrive on time, and share your trip plan with someone you trust.</p></div>',unsafe_allow_html=True)
    st.markdown("### Quick actions")
    q1,q2,q3=st.columns(3)
    if q1.button("🧭 Find a ride",use_container_width=True): set_page("Explore rides"); st.rerun()
    if q2.button("🚗 Offer a seat",use_container_width=True): set_page("Offer a ride"); st.rerun()
    if q3.button("🛟 Safety centre",use_container_width=True): set_page("Safety & help"); st.rerun()

# ---------- Bookings ----------
def bookings_page():
    u=current_user(); hero("YOUR TRAVEL PLANS","My bookings 🎟️","Keep the details close. If plans change, cancel early so another student can use the seat.")
    rows=query("""SELECT b.*,r.from_place,r.to_place,r.ride_date,r.ride_time,r.fare,r.vehicle,r.notes,r.driver_id,r.status ride_status,
                  d.name driver_name,d.phone driver_phone FROM bookings b JOIN rides r ON r.id=b.ride_id JOIN users d ON d.id=r.driver_id
                  WHERE b.passenger_id=? ORDER BY b.created_at DESC""",(u["id"],))
    if not rows: st.info("No bookings yet. Your next ride is waiting in Explore rides."); return
    for r in rows:
        with st.container(border=True):
            x,y=st.columns([4,1])
            with x:
                st.markdown(f"**{safe(r['from_place'])}** → **{safe(r['to_place'])}**")
                st.caption(f"{nice_date(r['ride_date'])} · {r['ride_time']} · {safe(r['vehicle'] or 'Vehicle not specified')}")
                st.write(f"Driver: **{safe(r['driver_name'])}** · Seats: {r['seats']} · Total shared cost: **{money(r['fare']*r['seats'])}**")
                if r["notes"]: st.caption(r["notes"])
                st.caption(f"Booking status: {r['status']} · Ride status: {r['ride_status']}")
            with y:
                if r["status"]=="Confirmed" and r["ride_status"]=="Open":
                    if st.button("Cancel booking",key=f"cancel_b_{r['id']}",use_container_width=True):
                        execute("UPDATE bookings SET status='Cancelled' WHERE id=?",(r["id"],))
                        execute("UPDATE rides SET seats_available=MIN(seats_total,seats_available+?) WHERE id=?",(r["seats"],r["ride_id"]))
                        notify(r["driver_id"],f"{u['name']} cancelled their booking for {r['to_place']}.")
                        st.session_state.flash="Booking cancelled; seats have been released."
                        st.rerun()
                if r["status"]=="Confirmed" and r["ride_status"]=="Open" and r["driver_id"]!=u["id"]:
                    with st.popover("⭐ Rate driver"):
                        rating=st.slider("Rating",1,5,5,key=f"rating_{r['id']}")
                        comment=st.text_input("Short review (optional)",key=f"comment_{r['id']}")
                        if st.button("Submit rating",key=f"submit_rating_{r['id']}"):
                            try:
                                execute("INSERT INTO reviews(ride_id,reviewer_id,target_id,rating,comment,created_at) VALUES(?,?,?,?,?,?)",(r["ride_id"],u["id"],r["driver_id"],rating,comment,now()))
                                st.success("Thanks for sharing feedback!")
                            except sqlite3.IntegrityError: st.warning("You have already rated this ride.")

# ---------- My rides ----------
def my_rides_page():
    u=current_user(); hero("YOUR ROUTES","My rides 🛣️","Manage the rides you publish. Keep seat counts and details accurate.")
    rows=query("SELECT * FROM rides WHERE driver_id=? ORDER BY created_at DESC",(u["id"],))
    if not rows: st.info("You haven't posted a ride yet."); 
    for r in rows:
        with st.container(border=True):
            a,b=st.columns([4,1])
            with a:
                st.markdown(f"**{safe(r['from_place'])}** → **{safe(r['to_place'])}**")
                st.caption(f"{nice_date(r['ride_date'])} · {r['ride_time']} · {r['seats_available']}/{r['seats_total']} seats left · {money(r['fare'])}/seat")
                st.caption(f"Status: {r['status']} · {safe(r['vehicle'] or 'No vehicle info')}")
                bs=query("""SELECT b.*,u.name,u.email FROM bookings b JOIN users u ON u.id=b.passenger_id WHERE b.ride_id=? AND b.status='Confirmed'""",(r["id"],))
                if bs:
                    with st.expander(f"Passengers ({len(bs)})"):
                        for p in bs: st.write(f"👤 {safe(p['name'])} · {p['seats']} seat(s) · {safe(p['email'])}")
            with b:
                if r["status"]=="Open" and st.button("Close ride",key=f"close_{r['id']}",use_container_width=True):
                    execute("UPDATE rides SET status='Closed' WHERE id=?",(r["id"],))
                    for bk in query("SELECT passenger_id FROM bookings WHERE ride_id=? AND status='Confirmed'",(r["id"],)):
                        notify(bk["passenger_id"],f"The ride to {r['to_place']} has been closed by the driver.")
                    st.session_state.flash="Ride closed. Existing bookings remain visible."
                    st.rerun()
                elif r["status"]=="Closed": st.caption("Closed")

# ---------- Notifications ----------
def notifications_page():
    u=current_user(); hero("NOTHING SLIPS THROUGH","Notifications 🔔","Booking updates and ride changes, all in one place.")
    rows=query("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC",(u["id"],))
    if not rows: st.info("You're all caught up. ✨"); return
    if st.button("Mark all as read"):
        execute("UPDATE notifications SET seen=1 WHERE user_id=?",(u["id"],)); st.rerun()
    for n in rows:
        with st.container(border=True):
            st.markdown(("🟢 " if not n["seen"] else "⚪ ")+safe(n["message"]))
            st.caption(n["created_at"].replace("T"," "))
            if not n["seen"] and st.button("Mark read",key=f"read_{n['id']}"):
                execute("UPDATE notifications SET seen=1 WHERE id=?",(n["id"],)); st.rerun()

# ---------- Safety ----------
def safety_page():
    hero("SAFETY IS A FEATURE","Travel smart. Get home safe. 🛟","RideBloom is a student coordination prototype—not an emergency dispatch service. Keep your own safety plan active.",["📍 Verify pickup","📞 Share trip","🤝 Meet in public"])
    a,b=st.columns(2)
    with a:
        st.markdown('<div class="rb-card"><div class="rb-card-title">Before you ride</div><p>✓ Confirm driver and vehicle details in person.<br/>✓ Meet at a well-lit, public pickup point.<br/>✓ Tell a trusted person your route and ETA.<br/>✓ Agree on cost before departure.<br/>✓ Wear a helmet/seat belt and follow traffic laws.</p></div>',unsafe_allow_html=True)
        st.markdown('<div class="rb-card"><div class="rb-card-title">Privacy basics</div><p>Only share the information needed to coordinate a ride. Never post passwords, OTPs, payment details, or your live location publicly.</p></div>',unsafe_allow_html=True)
    with b:
        st.markdown('<div class="rb-card"><div class="rb-card-title">🚨 Need urgent help?</div><p>Use your phone to contact local emergency services or a trusted person. In India, call <b>112</b> for emergency assistance. The SOS button below only records a local in-app alert; it does not contact police or send GPS coordinates.</p></div>',unsafe_allow_html=True)
        if st.button("Create in-app safety alert",use_container_width=True):
            execute("INSERT INTO notifications(user_id,message,created_at) VALUES(?,?,?)",(current_user()["id"],"Safety alert created by you. This is a local app notification only; no emergency service was contacted.",now()))
            st.warning("Local alert recorded only. This did NOT contact emergency services.")
        st.markdown("### Quick checklist")
        for item in ["Driver and vehicle match the details","Pickup point is public and well-lit","Trusted contact knows my plan","Fare is agreed before departure"]:
            st.checkbox(item,key="safe_"+item)

# ---------- Profile ----------
def profile_page():
    u=current_user(); hero("YOUR CAMPUS IDENTITY","Profile & preferences 🌱","Keep your basic details current so your ride community knows who they are coordinating with.")
    with st.form("profile_form"):
        a,b=st.columns(2)
        name=a.text_input("Full name",value=u["name"])
        phone=b.text_input("Phone",value=u["phone"] or "")
        dept=a.selectbox("Department",["AI & DS","CSE","IT","ENTC","Mechanical","Civil","Other"],index=["AI & DS","CSE","IT","ENTC","Mechanical","Civil","Other"].index(u["department"]) if u["department"] in ["AI & DS","CSE","IT","ENTC","Mechanical","Civil","Other"] else 0)
        year=b.selectbox("Study year",["First Year","Second Year","Third Year","Final Year","Postgraduate"],index=["First Year","Second Year","Third Year","Final Year","Postgraduate"].index(u["year"]) if u["year"] in ["First Year","Second Year","Third Year","Final Year","Postgraduate"] else 0)
        st.text_input("Email (login ID)",value=u["email"],disabled=True)
        st.text_input("College ID",value=u["student_id"],disabled=True)
        save=st.form_submit_button("Save profile")
    if save:
        execute("UPDATE users SET name=?,phone=?,department=?,year=? WHERE id=?",(name.strip(),phone.strip(),dept,year,u["id"]))
        st.session_state.flash="Profile updated."; st.rerun()
    st.markdown("### Account security")
    with st.form("password_form"):
        old=st.text_input("Current password",type="password")
        new=st.text_input("New password (8+ characters)",type="password")
        confirm=st.text_input("Confirm new password",type="password")
        change=st.form_submit_button("Update password")
    if change:
        fresh=get_user(u["id"])
        if fresh["password_hash"]!=password_hash(old): st.error("Current password is incorrect.")
        elif len(new)<8: st.error("New password must be at least 8 characters.")
        elif new!=confirm: st.error("New passwords do not match.")
        else:
            execute("UPDATE users SET password_hash=? WHERE id=?",(password_hash(new),u["id"]))
            st.success("Password updated.")

# ---------- Routing ----------
page=st.session_state.page
if not current_user() and page not in ["Sign in","Explore rides"]:
    page="Sign in"; st.session_state.page=page
if page=="Sign in": auth_page()
elif page=="Overview": overview_page()
elif page=="Explore rides": explore_page()
elif page=="Offer a ride": offer_page()
elif page=="My bookings": bookings_page()
elif page=="My rides": my_rides_page()
elif page=="Notifications": notifications_page()
elif page=="Safety & help": safety_page()
elif page=="Profile": profile_page()
else: explore_page()

st.markdown('<div class="rb-footer">RideBloom · College Ride Sharing Prototype<br/>Prototype safety note: student verification is currently based on entered college ID, not an institutional identity provider.</div>',unsafe_allow_html=True)
