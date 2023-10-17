from notion_scraper import *

# Initialize a NotionPage object with the URL of the page you want to scrape
page = NotionPage("https://chiefaioffice.notion.site/MindsDB-fd7a0899b9ba4b348e90ddc95bbca36e")

# Scrape the page
page.scrape()

# Get the JSON output
json_output = page.get_json()

# Print the JSON output
print(json_output)