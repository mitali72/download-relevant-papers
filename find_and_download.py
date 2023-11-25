import os
import re
import wget
import requests

S2_API_KEY = os.getenv('S2_API_KEY')


def main():
    find_basis_paper()


def find_basis_paper(result_limit = 10):
    papers = None
    while not papers:
        query = input('Find papers about what: ')
        if not query:
            continue
        
        params = {'query': query, 'limit': result_limit, 'fields': 'title,isOpenAccess,openAccessPdf', 'openAccessPdf': None}
        params = '&'.join([k if v is None else f"{k}={v}" for k, v in params.items()])

        rsp = requests.get('https://api.semanticscholar.org/graph/v1/paper/search',
                           headers={'X-API-KEY': S2_API_KEY},
                           params=params)
        print(rsp.url)
        rsp.raise_for_status()
        results = rsp.json()
        total = results["total"]
        if not total:
            print('No matches found. Please try another query.')
            continue

        print(f'Found {total} results. Showing up to {result_limit}.')
        papers = results['data']
        print_papers(papers)

    
        indices= input(f"Select paper indices to review? (Give indices. Eg. 0 1)\n")
        indices = list(map(int,indices.split()))

        if not os.path.exists("papers"):
            os.makedirs("./papers")

        for index in indices:
            try:
                wget.download(papers[index]['openAccessPdf']['url'], os.path.join("papers",f"user_paper{index}.pdf"))
            except:
                print(f"Need access to the paper, Pls download manually for review: {papers[index]['openAccessPdf']['url']}")


def print_papers(papers):
    for idx, paper in enumerate(papers):
        print(f"{idx}  {paper['title']} {paper['openAccessPdf']['url']}")


if __name__ == '__main__':
    main()