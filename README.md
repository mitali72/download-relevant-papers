# Download Top Relevant Papers using Evadb

# Overview:
This app allows the user to download top papers, top tools, top datasets relevant to a given input paper.

# Setup:
1. Follow getting started at https://evadb.readthedocs.io/en/stable/source/overview/getting-started.html for env and evadb setup.
2. pip install -r requirements.txt

Make sure you have papers and rel_papers directory created in the parent folder.
* "papers" directory should contain the papers you want to query for.
* Relevant papers will be downloaded in "rel_papers".

Note: You will need OpenAI API key to use this APP.

# Run:
1. To download top relevant papers:\
python3 relevant_papers.py

You can check the frequency of each paper found in the top_rel_papers.json file.
