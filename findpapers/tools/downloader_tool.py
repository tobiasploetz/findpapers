import os
import re
import json
import requests
import logging
import datetime
import urllib.parse
from findpapers.models.paper import Paper
from lxml import html
from typing import Optional, List
import findpapers.utils.common_util as common_util
import findpapers.utils.persistence_util as persistence_util
from findpapers.models.search import Search
from findpapers.utils.requests_util import DefaultSession


def get_default_filebasename(paper: Paper) -> str:
    filename = f"{paper.publication_date.year}-{paper.title}"
    filename = re.sub(r"[^\w\d-]", "_", filename)  # sanitize filename
    return filename


def find_pdf_url(paper: Paper) -> Optional[str]:
    pdf_url = None
    for (
        url
    ) in paper.urls:  # we'll try to download the PDF file of the paper by its URLs
        try:
            logging.info(f"Fetching data from: {url}")

            response = common_util.try_success(
                lambda url=url: DefaultSession().head(url, allow_redirects=True), 2
            )

            if response is None:
                continue

            if "text/html" in response.headers.get("content-type").lower():
                response_url = urllib.parse.urlsplit(response.url)
                response_query_string = urllib.parse.parse_qs(
                    urllib.parse.urlparse(response.url).query
                )
                response_url_path = response_url.path
                host_url = f"{response_url.scheme}://{response_url.hostname}"
                pdf_url = None

                if response_url_path.endswith("/"):
                    response_url_path = response_url_path[:-1]

                response_url_path = response_url_path.split("?")[0]

                if host_url in ["https://dl.acm.org"]:
                    doi = paper.doi
                    if (
                        doi is None
                        and response_url_path.startswith("/doi/")
                        and "/doi/pdf/" not in response_url_path
                    ):
                        doi = response_url_path[4:]
                    elif doi is None:
                        continue

                    pdf_url = f"https://dl.acm.org/doi/pdf/{doi}"

                elif host_url in ["https://ieeexplore.ieee.org"]:
                    if response_url_path.startswith("/document/"):
                        document_id = response_url_path[10:]
                    elif response_query_string.get("arnumber", None) is not None:
                        document_id = response_query_string.get("arnumber")[0]
                    else:
                        continue

                    pdf_url = (
                        f"{host_url}/stampPDF/getPDF.jsp?tp=&arnumber={document_id}"
                    )

                elif host_url in [
                    "https://www.sciencedirect.com",
                    "https://linkinghub.elsevier.com",
                ]:
                    paper_id = response_url_path.split("/")[-1]
                    pdf_url = f"https://www.sciencedirect.com/science/article/pii/{paper_id}/pdfft?isDTMRedir=true&download=true"

                elif host_url in ["https://pubs.rsc.org"]:
                    pdf_url = response.url.replace("/articlelanding/", "/articlepdf/")

                elif host_url in [
                    "https://www.tandfonline.com",
                    "https://www.frontiersin.org",
                ]:
                    pdf_url = response.url.replace("/full", "/pdf")

                elif host_url in [
                    "https://pubs.acs.org",
                    "https://journals.sagepub.com",
                    "https://royalsocietypublishing.org",
                ]:
                    pdf_url = response.url.replace("/doi", "/doi/pdf")

                elif host_url in ["https://link.springer.com"]:
                    pdf_url = (
                        response.url.replace("/article/", "/content/pdf/").replace(
                            "%2F", "/"
                        )
                        + ".pdf"
                    )

                elif host_url in ["https://www.isca-speech.org"]:
                    pdf_url = response.url.replace("/abstracts/", "/pdfs/").replace(
                        ".html", ".pdf"
                    )

                elif host_url in ["https://onlinelibrary.wiley.com"]:
                    pdf_url = response.url.replace("/full/", "/pdfdirect/").replace(
                        "/abs/", "/pdfdirect/"
                    )

                elif host_url in ["https://www.jmir.org", "https://www.mdpi.com"]:
                    pdf_url = response.url + "/pdf"

                elif host_url in ["https://www.pnas.org"]:
                    pdf_url = (
                        response.url.replace("/content/", "/content/pnas/")
                        + ".full.pdf"
                    )

                elif host_url in ["https://www.jneurosci.org"]:
                    pdf_url = (
                        response.url.replace("/content/", "/content/jneuro/")
                        + ".full.pdf"
                    )

                elif host_url in ["https://www.ijcai.org"]:
                    paper_id = response.url.split("/")[-1].zfill(4)
                    pdf_url = (
                        "/".join(response.url.split("/")[:-1]) + "/" + paper_id + ".pdf"
                    )

                elif host_url in ["https://asmp-eurasipjournals.springeropen.com"]:
                    pdf_url = response.url.replace("/articles/", "/track/pdf/")

            elif "application/pdf" in response.headers.get("content-type").lower():
                pdf_url = response.url

        except Exception as e:  # pragma: no cover
            logging.debug(e, exc_info=True)

        if pdf_url is not None:
            break

    return pdf_url


def download_paper(paper: Paper, output_directory: str, output_filename=None) -> str:
    """
    Download the PDF file of a paper to the output directory path.

    Parameters
    ----------
    paper : Paper
        A paper instance
    output_directory : str
        A valid file path of the directory where the downloaded paper will be placed
    output_filename : Optional[str], optional
        The output filename, by default None

    Returns
    -------
    str
        The output filepath
    """
    if output_filename is None:
        output_filename = get_default_filebasename(paper)
        output_filename += ".pdf"

    output_filepath = os.path.join(output_directory, output_filename)

    if os.path.exists(output_filepath):  # PDF already collected
        logging.info(f"Paper's PDF file has already been collected")
        return output_filepath

    if paper.pdf_url is None:
        paper.pdf_url = find_pdf_url(paper)

    if paper.pdf_url is not None:
        response = common_util.try_success(
            lambda url=paper.pdf_url: DefaultSession().get(url), 2
        )
        if "application/pdf" in response.headers.get("content-type").lower():
            with open(output_filepath, "wb") as fp:
                fp.write(response.content)
        return output_filepath
    else:
        logging.info(f"Paper's PDF file cannot be collected")
        return None


def download(
    search_path: str,
    output_directory: str,
    only_selected_papers: Optional[bool] = False,
    categories_filter: Optional[dict] = None,
    proxy: Optional[str] = None,
    verbose: Optional[bool] = False,
):
    """
    If you've done your search, (probably made the search refinement too) and wanna download the papers,
    this is the method that you need to call. This method will try to download the PDF version of the papers to
    the output directory path.

    We use some heuristics to do our job, but sometime they won't work properly, and we cannot be able
    to download the papers, but we logging the downloads or failures in a file download.log
    placed on the output directory, you can check out the log to find what papers cannot be downloaded
    and try to get them manually later.

    Note: Some papers are behind a paywall and won't be able to be downloaded by this method.
    However, if you have a proxy provided for the institution where you study or work that permit you
    to "break" this paywall. You can use this proxy configuration here
    by setting the environment variables FINDPAPERS_HTTP_PROXY and FINDPAPERS_HTTPS_PROXY.

    Parameters
    ----------
    search_path : str
        A valid file path containing a JSON representation of the search results
    output_directory : str
        A valid file path of the directory where the downloaded papers will be placed
    only_selected_papers : bool, False by default
        If only the selected papers will be downloaded
    categories_filter : dict, None by default
        A dict of categories to be used to filter which papers will be downloaded
    proxy : Optional[str], optional
        proxy URL that can be used during requests. This can be also defined by an environment variable FINDPAPERS_PROXY. By default None
    verbose : Optional[bool], optional
        If you wanna a verbose logging
    """

    common_util.logging_initialize(verbose)

    if proxy is not None:
        os.environ["FINDPAPERS_PROXY"] = proxy

    search = persistence_util.load(search_path)

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    log_filepath = os.path.join(output_directory, "download.log")

    common_util.check_write_access(log_filepath)

    with open(log_filepath, "a" if os.path.exists(log_filepath) else "w") as fp:
        now = datetime.datetime.now()
        fp.write(
            f"------- A new download process started at: {datetime.datetime.strftime(now, '%Y-%m-%d %H:%M:%S')} \n"
        )

    for i, paper in enumerate(search.papers):
        logging.info(f"({i+1}/{len(search.papers)}) {paper.title}")

        if (only_selected_papers and not paper.selected) or (
            categories_filter is not None
            and (
                paper.categories is None
                or not paper.has_category_match(categories_filter)
            )
        ):
            continue

        output_filepath = download_paper(paper, output_directory)
        downloaded = output_filepath is not None

        if downloaded:
            paper.file_path = output_filepath
            with open(log_filepath, "a") as fp:
                fp.write(f"[DOWNLOADED] {paper.title}\n")
        else:
            with open(log_filepath, "a") as fp:
                fp.write(f"[FAILED] {paper.title}\n")
                if len(paper.urls) == 0:
                    fp.write(f"Empty URL list\n")
                else:
                    for url in paper.urls:
                        fp.write(f"{url}\n")
