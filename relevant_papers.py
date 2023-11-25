import os
import requests
import pandas as pd
import evadb
import wget
import warnings
import json
import shutil

S2_API_KEY = os.getenv('S2_API_KEY')
PER_PAGE_PATH = os.path.join("evadb_data", "tmp", "page_wise_data.csv")
REL_PAPERS_PATH = os.path.join("evadb_data", "tmp", "top_rel_papers.csv")

def receive_user_input():

    user_input = {}

    paper_name = input("Enter the file name of the paper you want to query: ")
    user_input['name'] = paper_name

    ref_pgs = input("Give the page numbers containing references. (10 11 12): ")
    ref_pgs = list(map(int,ref_pgs.split()))
    user_input['ref_pgs'] = ref_pgs

    # get OpenAI key if needed
    try:
        api_key = os.environ["OPENAI_KEY"]
    except KeyError:
        api_key = str(input("🔑 Enter your OpenAI key: "))
        os.environ["OPENAI_KEY"] = api_key

    return user_input


def save_per_page_data(args):
    # create table to load pdfs
    cursor.query("DROP TABLE IF EXISTS MyPDFs").df()

    cursor.query(f"LOAD PDF '{os.path.join('papers',args['name'])}' INTO MyPDFs").df()

    data = cursor.query(f"""
        SELECT *
        FROM MyPDFs
        """).df()
    
    data = data.groupby(['mypdfs.page'])['mypdfs.data'].apply(lambda x: '. '.join(x)).reset_index()
    data.to_csv(PER_PAGE_PATH, header=['id', 'data'])


def find_top_relevant_papers(user_input):


    cursor.query("DROP TABLE IF EXISTS PageWiseData").df()
    cursor.query(f"""
    CREATE TABLE PageWiseData
    (id INTEGER,
    data TEXT(6192));
    """).df()

    cursor.load(PER_PAGE_PATH, "PageWiseData", "csv").execute()

    data = cursor.query(f"""
        SELECT *
        FROM PageWiseData
        """).df()
    
    # print(data)

    page_query = ""
    for page_num in user_input['ref_pgs']:
        if (page_query != ""):
            page_query += " OR "
        page_query += f"id = {page_num}"

    all_refs_df = cursor.query(f"""
        SELECT *
        FROM PageWiseData
        WHERE {page_query}
        """).df()
    
    all_refs = '\r\n'.join(all_refs_df['pagewisedata.data'].tolist())

    # rel_prompt = """You are provided a page from a research paper. Your goal is to find the 3 most relevant papers cited or referred directly, or compared indirectly in the provided text. Answer in one word for each relevant paper. Separate answers by comma."""

    rel_prompt = f"""Consider the below list of references:

{all_refs}
    
Next you are provided a page from a research paper. Your goal is to find the 3 most relevant papers cited or referred directly, or compared indirectly in the provided text. Answer in one word for each. Find the title of the reference paper for each using the list of references given above. Return the answer as a dictionary only, where the key is relevant paper and value is the paper title. Here is an example (use it only for the output format, not for the content):

{{"COCO": "Microsoft COCO: Common objects in context. In: ECCV (2014)"}}"""

    tool_prompt = """You are given a page from a research paper. What is the most important tool used for implementation in the given text. Answer in one word."""

    dataset_prompt = """You are given a page from a research paper. What is the most important dataset or test suite used for experiments in the given text. Answer in one word."""

    resps_paper = []
    resps_tool = []
    resps_dataset = []

    for index, row in data.iterrows():

        if(index+1 in user_input['ref_pgs']):
            continue
        
        # print(index)
        gen_rel_paper = cursor.query(
                f"""
                SELECT ChatGPT('{rel_prompt}', data)
                FROM PageWiseData
                WHERE id = {row["pagewisedata.id"]}
            """
            ).df()
        
        
        gen_tool = cursor.query(
                f"""
                SELECT ChatGPT("{tool_prompt}", data)
                FROM PageWiseData
                WHERE id = {row["pagewisedata.id"]}
            """
            ).df()
        
        gen_dataset = cursor.query(
                f"""
                SELECT ChatGPT("{dataset_prompt}", data)
                FROM PageWiseData
                WHERE id = {row["pagewisedata.id"]}
            """
            ).df()
        
        print(gen_rel_paper.iloc[0]["chatgpt.response"])
        resps_paper.append(gen_rel_paper.iloc[0]["chatgpt.response"])

        print(gen_tool.iloc[0]["chatgpt.response"])
        resps_tool.append(gen_tool.iloc[0]["chatgpt.response"])

        print(gen_dataset.iloc[0]["chatgpt.response"])
        resps_dataset.append(gen_dataset.iloc[0]["chatgpt.response"])
        break
    
    resps = {"papers": resps_paper, "tools": resps_tool, "datasets": resps_dataset}
    # resps = {"papers": resps_paper}

    resp_df = pd.DataFrame(resps)
    resp_df.to_csv(REL_PAPERS_PATH)

    top_rel_papers = {}
    top_rel_papers_freq = {}

    top_tool_freq = {}
    top_dataset_freq = {}

    for index, row in resp_df.iterrows():

        # relevant papers
        top_papers_pg = json.loads(row["papers"])

        for paper in top_papers_pg:
            if(len(top_papers_pg[paper])>150):
                continue

            paper_low = paper.lower()
            if paper_low in top_rel_papers:
                top_rel_papers_freq[paper_low] += 1
            else:
                top_rel_papers_freq[paper_low] = 1
                top_rel_papers[paper_low] = top_papers_pg[paper].split('. ')[0]

        # top tools
        top_tool_pg = row["tools"]
        if(len(top_tool_pg)<15):

            tool_low = top_tool_pg.lower()
            if tool_low in top_tool_freq:
                top_tool_freq[tool_low] += 1
            else:
                top_tool_freq[tool_low] = 1

        # top datasets
        top_dataset_pg = row["datasets"]
        if(len(top_dataset_pg)<30):

            dataset_low = top_dataset_pg.lower()
            if dataset_low in top_dataset_freq:
                top_dataset_freq[dataset_low] += 1
            else:
                top_dataset_freq[dataset_low] = 1


    with open('top_rel_papers.json', 'w') as fp:
        json.dump(top_rel_papers_freq, fp)

    with open('top_tools.json', 'w') as fp:
        json.dump(top_tool_freq, fp)

    with open('top_datasets.json', 'w') as fp:
        json.dump(top_dataset_freq, fp)

    
    #papers
    top_freq = []
    for paper in top_rel_papers_freq:
        top_freq.append([top_rel_papers_freq[paper],paper])

    top_freq.sort(key=lambda element:element[0], reverse=True)

    top_ans = {}
    print("The top 3 relevant papers are")
    for i in range(min(3,len(top_freq))):
        top_ans[top_freq[i][1]] = top_rel_papers[top_freq[i][1]]
        print(f"{top_freq[i][1]}: {top_rel_papers[top_freq[i][1]]}")
    print()


    top3(top_tool_freq,"tools")
    top3(top_dataset_freq,"datasets")
    
    return top_ans

def print_papers(papers):
    for idx, paper in enumerate(papers):
        print(f"Found {paper['title']} {paper['openAccessPdf']['url']}")


def get_papers(params):
    print("DOWNLOADING top relevant papers")
  
   
    params = '&'.join([k if v is None else f"{k}={v}" for k, v in params.items()])

    rsp = requests.get('https://api.semanticscholar.org/graph/v1/paper/search',
                        headers={'X-API-KEY': S2_API_KEY},
                        params=params)

    rsp.raise_for_status()
    results = rsp.json()
    total = results["total"]

    if not total:
        return None

    papers = results['data']
    return papers

def download_rel_papers(rel_paper_dict, download_path = "rel_papers", file_name = ""):
    
    for paper in rel_paper_dict:
        params = {'query': rel_paper_dict[paper], 'limit': 1, 'fields': 'title,isOpenAccess,openAccessPdf'}

        papers = get_papers(params)

        if papers is None:
            print('No matches found or need access to paper. Please try another query.')
            continue

        if not papers[0]['isOpenAccess']:
            print(f"Need access to the paper: {paper}, Pls download manually.")
            toDownload = input("Do you want to download any other top open access paper similar to this? (yes or no): ")
            if toDownload=="yes":
                params = {'query': paper, 'limit': 1, 'fields': 'title,isOpenAccess,openAccessPdf', 'openAccessPdf': None}
                papers = get_papers(params)
            else:
                continue


        if not os.path.exists(download_path):
            os.makedirs(download_path)

        print_papers(papers)

        try:
            wget.download(papers[0]['openAccessPdf']['url'], os.path.join(download_path, '_'.join(paper.split())+".pdf"))
        except:
            print(f"Need access to the paper: {paper}, Pls download manually: {papers[0]['openAccessPdf']['url']}")
   

def top3(freq_dict, artifact):
    # tools or datasets
    top_freq = []
    for key in freq_dict:
        top_freq.append([freq_dict[key],key])

    top_freq.sort(key=lambda element:element[0], reverse=True)

    print(f"The top {artifact} are")
    for i in range(min(3,len(top_freq))):
        print(top_freq[i][1])

    print()

def cleanup():
    """Removes any temporary file / directory created by EvaDB."""
    if os.path.exists("evadb_data"):
        shutil.rmtree("evadb_data")

if __name__=="__main__":
    
    warnings.filterwarnings("ignore")

    # receive input from user
    user_input = receive_user_input()

    try:
        # establish evadb api cursor
        cursor = evadb.connect().cursor()
        save_per_page_data(user_input)
        rel_papers = find_top_relevant_papers(user_input)
        download_rel_papers(rel_papers, "rel_papers")

    except Exception as e:
        cleanup()
        print("❗️ Session ended with an error.")
        print(e)
        print("===========================================")