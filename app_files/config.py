# Configuration for the Social Media Automator

# !!! IMPORTANT: Replace this with the actual URL of the target website !!!
TARGET_WEBSITE_URL = "https://dogehype.com/" # Or the specific page for automation

# --- UI Options --- 
PLATFORM_OPTIONS = ["Instagram", "TikTok", "YouTube", "X (Twitter)"]
# Basic engagement options - UI updates these based on platform
ENGAGEMENT_OPTIONS = ["Likes", "Views", "Shares", "Saves", "Reach/Impressions"]

# --- Dogehype Service Mapping --- 
# Mapping from (UI Platform, UI Engagement) to the EXACT text 
# needed in the Dogehype 'Category' dropdown.
# !!! This needs expansion for other services based on inspection of Dogehype !!!
CATEGORY_MAPPING = {
    # --- Instagram --- 
    ("Instagram", "Likes"): "Instagram - Likes - [RECOMMENDED]",
    ("Instagram", "Views"): "Instagram - Views",
    ("Instagram", "Reach/Impressions"): "Instagram - Reach | Engagement | Profile Visits | Shares",
    ("Instagram", "Saves"): "Instagram Saves",
    ("Instagram", "Shares"): "Instagram - Reach | Engagement | Profile Visits | Shares",
    
    # --- TikTok --- 
    ("TikTok", "Likes"): "TikTok - [LIKES]",
    ("TikTok", "Views"): "TikTok - [Views]",
    ("TikTok", "Shares"): "TikTok - [Shares | Saves]",
    ("TikTok", "Saves"): "TikTok - [Shares | Saves]",

    # --- YouTube --- 
    ("YouTube", "Likes"): "YouTube👍Likes",
    ("YouTube", "Views"): "YouTube👀Views - [Non-DROP]",
    ("YouTube", "Subscribers"): "YouTube💎Subscribers",
    ("YouTube", "Shares"): "YouTube💎Share to social networks",
    
    # --- X (Twitter) --- 
    ("X (Twitter)", "Likes"): "Twitter Likes",
    ("X (Twitter)", "Retweets"): "Twitter Retweets",
    ("X (Twitter)", "Views"): "Twitter Views",
}

# --- Minimum Order Quantities --- 
# Mapping from (UI Platform, UI Engagement) to the minimum quantity allowed by Dogehype
# !!! Verify these values on Dogehype for each service !!!
MINIMUM_QUANTITIES = {
    ("Instagram", "Likes"): 10,
    ("Instagram", "Views"): 100,
    ("Instagram", "Reach/Impressions"): 10,
    ("Instagram", "Shares"): 10,
    ("Instagram", "Saves"): 10,

    ("TikTok", "Likes"): 20,
    ("TikTok", "Views"): 100,
    ("TikTok", "Shares"): 10,
    ("TikTok", "Saves"): 10,

    ("YouTube", "Likes"): 20,
    ("YouTube", "Views"): 100,
    ("YouTube", "Subscribers"): 10,
    ("YouTube", "Shares"): 10,

    ("X (Twitter)", "Likes"): 10,
    ("X (Twitter)", "Retweets"): 10,
    ("X (Twitter)", "Views"): 50,
}

# You can add other configuration variables here later 