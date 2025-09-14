import os
import time
import json
import re
import csv
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable

import requests
import streamlit as st
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LinkedInProfileExtractor:
	"""Extract profile information from LinkedIn search results"""

	@staticmethod
	def extract_profile_info(search_result: Dict) -> Dict:
		"""
		Extract profile information from a single search result

		Returns:
			Dict with keys: name, title, link, description, image
		"""
		# Extract name from title (usually in format "Name - Title | LinkedIn")
		title_text = search_result.get('title', '')
		name = LinkedInProfileExtractor._extract_name_from_title(title_text)

		# Extract professional title
		professional_title = LinkedInProfileExtractor._extract_title_from_content(
			title_text, search_result.get('snippet', '')
		)

		# Extract image URL from pagemap
		image_url = LinkedInProfileExtractor._extract_image_url(search_result)

		# Clean and extract description
		description = LinkedInProfileExtractor._clean_description(
			search_result.get('snippet', '')
		)

		return {
			'name': name,
			'title': professional_title,
			'link': search_result.get('link', ''),
			'description': description,
			'image': image_url,
		}

	@staticmethod
	def _extract_name_from_title(title: str) -> str:
		"""Extract name from LinkedIn title"""
		if not title:
			return "N/A"

		# Remove " | LinkedIn" suffix
		title = title.replace(" | LinkedIn", "")

		# Split by " - " and take the first part as name
		parts = title.split(" - ")
		if parts:
			name = parts[0].strip()
			# Remove common prefixes/suffixes
			name = re.sub(r'^(Dr\.?|Mr\.?|Ms\.?|Mrs\.?)\s+', '', name)
			return name

		return title.strip()

	@staticmethod
	def _extract_title_from_content(title: str, snippet: str) -> str:
		"""Extract professional title from title and snippet"""
		# First try to extract from title (after the " - ")
		if " - " in title:
			parts = title.split(" - ")
			if len(parts) > 1:
				# Take everything after first " - " but before " | LinkedIn"
				professional_title = parts[1].replace(" | LinkedIn", "").strip()
				if professional_title:
					return professional_title

		# If not found in title, look for patterns in snippet
		snippet_lines = snippet.split(' · ')
		for line in snippet_lines:
			line = line.strip()
			# Look for common job title patterns
			if any(keyword in line.lower() for keyword in [
				'manager', 'director', 'engineer', 'analyst', 'specialist',
				'coordinator', 'executive', 'consultant', 'senior', 'lead'
			]):
				return line

		# Return first line of snippet if nothing else found
		first_line = snippet.split('.')[0].strip() if snippet else ""
		return first_line if first_line else "N/A"

	@staticmethod
	def _extract_image_url(search_result: Dict) -> str:
		"""Extract profile image URL"""
		try:
			pagemap = search_result.get('pagemap', {})

			# Try cse_image first
			if 'cse_image' in pagemap and pagemap['cse_image']:
				return pagemap['cse_image'][0].get('src', '')

			# Try metatags og:image
			if 'metatags' in pagemap and pagemap['metatags']:
				metatag = pagemap['metatags'][0]
				return metatag.get('og:image', '')

		except (KeyError, IndexError, TypeError):
			pass

		return ""

	@staticmethod
	def _clean_description(snippet: str) -> str:
		"""Clean and format description"""
		if not snippet:
			return "N/A"

		# Remove HTML entities
		snippet = snippet.replace('&amp;', '&').replace('&nbsp;', ' ')

		# Remove extra whitespace and normalize
		snippet = ' '.join(snippet.split())

		# Limit length
		if len(snippet) > 300:
			snippet = snippet[:300] + "..."

		return snippet


class GoogleSearchAPI:
	def __init__(self, api_key: str, search_engine_id: str):
		"""
		Initialize Google Custom Search API client

		Args:
			api_key: Your Google API key
			search_engine_id: Your Custom Search Engine ID (CX)
		"""
		self.api_key = api_key
		self.search_engine_id = search_engine_id
		self.base_url = "https://www.googleapis.com/customsearch/v1"
		self.results_per_page = 10  # Google's default and maximum for free tier

	def search(
		self,
		query: str,
		max_pages: int = 1,
		delay_seconds: int = 5,
		progress_callback: Optional[Callable[[int, int, int], None]] = None,
		**kwargs,
	) -> List[Dict]:
		"""
		Perform paginated Google Custom Search

		Args:
			query: Search query string
			max_pages: Maximum number of pages to fetch
			delay_seconds: Delay between requests (seconds)
			progress_callback: Optional callback with signature (page, max_pages, total_items_so_far)
			**kwargs: Additional search parameters (lr, gl, hl, etc.)

		Returns:
			List of all search results across all pages
		"""
		all_results: List[Dict] = []

		for page in range(1, max_pages + 1):
			if progress_callback is not None:
				progress_callback(page - 1, max_pages, len(all_results))

			logger.info(f"Fetching page {page}/{max_pages}")

			# Calculate start index (Google uses 1-based indexing)
			start_index = (page - 1) * self.results_per_page + 1

			try:
				# Make API request
				results = self._make_request(query, start_index, **kwargs)

				if not results:
					logger.warning(f"No results returned for page {page}")
					break

				# Extract search items
				items = results.get('items', [])
				if not items:
					logger.info(f"No more results available after page {page - 1}")
					break

				# Add page info to each result
				for item in items:
					item['page_number'] = page
					item['result_index'] = len(all_results) + 1

				all_results.extend(items)
				logger.info(f"Page {page}: Retrieved {len(items)} results")

			except Exception as e:
				logger.error(f"Error fetching page {page}: {str(e)}")
				break

			# Delay between requests (except for last page)
			if page < max_pages and delay_seconds > 0:
				logger.info(f"Waiting {delay_seconds} seconds before next request...")
				time.sleep(delay_seconds)

			if progress_callback is not None:
				progress_callback(page, max_pages, len(all_results))

		logger.info(f"Search completed. Total results fetched: {len(all_results)}")
		return all_results

	def _make_request(self, query: str, start: int = 1, **kwargs) -> Optional[Dict]:
		"""
		Make a single API request to Google Custom Search
		"""
		params = {
			'key': self.api_key,
			'cx': self.search_engine_id,
			'q': query,
			'start': start,
			'num': self.results_per_page,
		}

		# Add additional parameters
		params.update(kwargs)

		try:
			response = requests.get(self.base_url, params=params, timeout=30)
			response.raise_for_status()

			return response.json()

		except requests.exceptions.RequestException as e:
			logger.error(f"Request failed: {str(e)}")
			if hasattr(e, 'response') and getattr(e.response, 'text', None):
				logger.error(f"Response: {e.response.text}")
			return None
		except json.JSONDecodeError as e:
			logger.error(f"JSON decode error: {str(e)}")
			return None


def profiles_to_dataframe(items: List[Dict]) -> pd.DataFrame:
	profiles = []
	for result in items:
		profile_info = LinkedInProfileExtractor.extract_profile_info(result)
		profiles.append(profile_info)
	return pd.DataFrame(profiles, columns=['name', 'title', 'link', 'description', 'image'])


def make_csv_bytes(df: pd.DataFrame) -> bytes:
	return df.rename(columns={
		'name': 'Name',
		'title': 'Title',
		'link': 'Link',
		'description': 'Description',
		'image': 'Image',
	}).to_csv(index=False).encode('utf-8')


def get_default_api_key() -> str:
	# Prefer Streamlit secrets, then env var, else empty
	return "AIzaSyBLtNfnghsBXgnZlixmhpQN5eStJNg72Y4"

def get_default_cse_id() -> str:
	return "305ab541cef5a4278"


st.set_page_config(page_title="LinkedIn Profile Finder", page_icon="🔎", layout="wide")

st.title("🔎 LinkedIn Profile Finder")

st.markdown(
	"Search Google for public LinkedIn profiles and export results to CSV."
)

with st.sidebar:
	st.header("Configuration")
	api_key = get_default_api_key()
	cse_id = get_default_cse_id()
	# api_key = st.text_input(
	# 	"Google API Key",
	# 	value=get_default_api_key(),
	# 	type="password",
	# 	help="Stored locally in this session. Prefer setting in Streamlit secrets or environment variables.",
	# )
	# cse_id = st.text_input(
	# 	"Custom Search Engine ID (CX)",
	# 	value=get_default_cse_id(),
	# 	help="Your Programmable Search Engine ID",
	# )
	max_pages = st.number_input("Pages to fetch (10 results per page)", min_value=1, max_value=10, value=3)
	delay_seconds = st.number_input("Delay between pages (seconds)", min_value=0, max_value=60, value=5)

col_q1, col_q2 = st.columns([2, 1])
with col_q1:
	query_input = st.text_input(
		"Search query (we will auto-append site:linkedin.com/in)",
		value="facility managers united kingdom",
		placeholder="e.g., data scientist berlin",
	)
with col_q2:
	start_button = st.button("Run Search", type="primary")

st.divider()

if 'results_df' not in st.session_state:
	st.session_state.results_df = None

if start_button:
	if not api_key or not cse_id:
		st.error("Please provide Google API Key and CSE ID.")
	else:
		# Build the query by hardcoding LinkedIn filter
		final_query = f"{query_input} site:linkedin.com/in"

		progress = st.progress(0, text="Starting search...")
		status_area = st.empty()

		def update_progress(curr_page: int, total_pages: int, total_items: int) -> None:
			# curr_page is pages completed; show fractional progress
			page_portion = min(max(curr_page / max(total_pages, 1), 0), 1)
			item_portion = min((total_items % 10) / 10, 1)
			percent = int(((curr_page) / total_pages) * 100) if total_pages > 0 else 0
			progress.progress(percent, text=f"Fetching page {min(curr_page + 1, total_pages)}/{total_pages} · items: {total_items}")
			status_area.info(f"Fetched {total_items} results across {curr_page}/{total_pages} pages")

		search_client = GoogleSearchAPI(api_key, cse_id)
		with st.spinner("Calling Google Custom Search API..."):
			results = search_client.search(
				query=final_query,
				max_pages=int(max_pages),
				delay_seconds=int(delay_seconds),
				progress_callback=update_progress,
			)

		if not results:
			progress.progress(100, text="Done")
			st.warning("No results found.")
			st.session_state.results_df = None
		else:
			# Convert to profiles and DataFrame
			profiles_df = profiles_to_dataframe(results)
			st.session_state.results_df = profiles_df
			progress.progress(100, text=f"Done · {len(profiles_df)} profiles")

if st.session_state.results_df is not None:
	st.subheader("Results")
	st.caption("Preview of extracted profiles")
	st.dataframe(
		st.session_state.results_df.rename(columns={
			'name': 'Name', 'title': 'Title', 'link': 'Link', 'description': 'Description', 'image': 'Image'
		}),
		use_container_width=True,
		hide_index=True,
	)

	csv_bytes = make_csv_bytes(st.session_state.results_df)
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	filename = f"LinkedIn_Profiles_{timestamp}.csv"
	st.download_button(
		label="Download CSV",
		data=csv_bytes,
		file_name=filename,
		mime="text/csv",
		type="primary",
	)

	with st.expander("First 3 profiles"):
		for i, row in st.session_state.results_df.head(3).iterrows():
			st.markdown(f"**{row['name']}** — {row['title']}")
			st.caption(row['link'])
			if row['image']:
				st.image(row['image'], width=80)
			st.divider() 