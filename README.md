# 🌼 RideBloom — College Ride Sharing App

A polished Streamlit prototype for the **Designing a Ride Sharing App for College Students** project. Built for student commute coordination with a warm, friendly dashboard and a free OpenStreetMap map.

## Features
- Student registration, login, profile editing, password update
- Ride search by destination and travel date
- Post rides with seat capacity, departure time, vehicle, fare share, notes
- Interactive OpenStreetMap pins for optional pickup/drop-off coordinates
- Seat booking, cancellation, live seat count updates
- Driver ride management and passenger list
- In-app notifications
- Driver ratings/reviews
- Safety checklist and local in-app alert
- Overview dashboard with useful metrics
- Demo rides seeded automatically on first run

## Run locally (Windows)
1. Install Python 3.10 or newer.
2. Extract the ZIP.
3. Open Command Prompt/PowerShell in this folder.
4. Run:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

On macOS/Linux, activate with `source .venv/bin/activate`.

## Demo login
- Email: `aarav.demo@ridebloom.local`
- Password: `Bloom@123`

Or register your own account.

## Deploy free with GitHub + Streamlit Community Cloud
1. Create a GitHub repository (public is simplest for a college demo).
2. Upload `app.py`, `requirements.txt`, and this README.
3. Open https://share.streamlit.io/ and sign in with GitHub.
4. Select the repository, branch, and `app.py`, then deploy.

No Google Maps API key or paid map service is used. Map tiles come from OpenStreetMap. Please follow the tile provider's usage policy and avoid heavy automated usage.

## Important deployment/data limitation
This starter stores records in a local SQLite database (`ridebloom.db`). It is excellent for a local demo and for testing a prototype. **Streamlit Community Cloud's local filesystem is not a reliable permanent shared database**; data may reset after a restart/redeploy, and multiple instances are not coordinated. For a real multi-student deployment with durable shared accounts/bookings, connect a free-tier hosted database such as Supabase (requires creating a project and adding secrets). Do not present the SQLite deployment as production-grade persistence.

## Safety and verification limitations
- College ID is collected but not verified against college records. It is a prototype, not institutional authentication.
- The SOS feature creates an in-app note only; it does not call emergency services, send SMS, or share GPS.
- Ratings are prototype-level. For a real deployment, add ride-completion rules, moderation, abuse prevention, secure password hashing, rate limiting, and privacy/security review.
- Do not enter sensitive or real emergency information in the demo.

## Project stack
- Python + Streamlit
- SQLite for prototype data
- Folium + OpenStreetMap for no-key map display
- Streamlit-Folium for interactive map pins

## Reset the local demo
Stop Streamlit, then delete `ridebloom.db`. It will be recreated with sample data next time the app starts.
