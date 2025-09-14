## LinkedIn Profile Finder (Streamlit)

Search Google Programmable Search for public LinkedIn profiles, preview results, and export to CSV. Includes progress, CSV download, and Docker support.

### Prerequisites
- Google API Key
- Google Programmable Search Engine (CSE) ID

### Configure credentials
Use either environment variables or Streamlit secrets.

- Environment variables:
```
set GOOGLE_API_KEY=your_api_key
set GOOGLE_CSE_ID=your_cse_id
```
On Linux/macOS:
```
export GOOGLE_API_KEY=your_api_key
export GOOGLE_CSE_ID=your_cse_id
```

- Or create `.streamlit/secrets.toml`:
```
GOOGLE_API_KEY = "your_api_key"
GOOGLE_CSE_ID = "your_cse_id"
```

### Install and run locally
```
pip install -r requirements.txt
streamlit run app.py
```
Open the app at http://localhost:8501

### Docker
Build and run:
```
docker build -t linkedin-finder .
```

- With env vars:
```
docker run --rm -p 8501:8501 \
  -e GOOGLE_API_KEY=your_api_key \
  -e GOOGLE_CSE_ID=your_cse_id \
  linkedin-finder
```

- Or mount secrets:
```
mkdir -p .streamlit
# create .streamlit/secrets.toml with keys

docker run --rm -p 8501:8501 \
  -v %cd%/.streamlit:/app/.streamlit \
  linkedin-finder
```

### Usage
- Enter your search terms; the app auto-appends `site:linkedin.com/in`
- Set number of pages (10 results per page) and delay between API calls
- Click Run Search to fetch results
- Preview the table, then click Download CSV

### Notes
- Scrapes metadata from Google search results; it does not log in to LinkedIn
- Respect API quotas and terms of service 