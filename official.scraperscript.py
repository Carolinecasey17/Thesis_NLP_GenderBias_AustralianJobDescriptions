# -*- coding: utf-8 -*-
"""
Python script of customised scraper for extracting job descriptions off the Australian au.indeed.com recruitment site. 

"""
# install packages 
from gettext import install

import pandas as pd

from bs4 import BeautifulSoup
import urllib.request, urllib.parse, urllib.error
import requests
import re

import scrapy
from scrapy.selector import Selector

import selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

import time
from time import sleep

import os

# setting link threshold so we don't keep searching indefinitely 
LINK_THRESHOLD = 6

# storing both selenium and request version to allow switching
url = "https://au.indeed.com/jobs?q=medical%20receptionist&l&vjk=c8832ffc85c840d5&advn=5398274479580380"

# install chromedriver 
CHROME_DRIVER = "C:/Users/kilda/OneDrive/THESIS/Scripts/chromedriver/chromedriver.exe"

def make_fresh_soup(url):

    """Function takes a url and returns a BeautifulSoup object"""

    # testing just using request
    response = requests.get(url)
    html = response.text

    # use driver and wait one second for javascript to run before capturing html
    s = Service(CHROME_DRIVER)

    # making it headless so chrome isn't opened on your pc
    opts = webdriver.ChromeOptions()
    opts.headless = False
    driver = webdriver.Chrome(service=s, options=opts)
    driver.get(url)
    sleep(1)

    html = driver.page_source

    # converting to soup object
    soup = BeautifulSoup(html)

    # closing the driver to keep things clean
    driver.close()

    return soup


def indeed_search(search_terms=['', ''], location=["", ""]):

    """Function takes lists of job search terms and optional location strings
    Returns the url for an indeed search for scraping
    Search_terms should be a list of terms e.g.['data','scientist']
    Location should be a list of city, state; ['Melbourne','VIC']
    In this script, we call the occupation and locations in later, to allow for searching multiple occupations and locations simultaneously"""

    # setting and formatting terms for search
    search_string = search_terms[0]
    for term in search_terms[1:]:
        search_string = search_string + "+" + term

    # adding location
    location_string = location[0] + "+" + location[1]
    search_string = search_string + "&l=" + location_string

    # setting url for scraping
    search_url = "https://au.indeed.com/jobs?q=" + search_string

    return search_url


def get_job_links(soup_search):

    """Function returns links to a job from an indeed search page"""

    links = [
        ("https://au.indeed.com" + job.get("href"))
        for job in soup_search.find_all("a", attrs={"id": re.compile("job\_*")})
        if job.get("href") is not None
    ]
    return links


def get_next_link(soup_search):

    """Function for extraxting the link to the next page of jobs in the search
    Accepts a BeautifulSoup object of the search page as input
    Returns the link to the next results page, or None on the last page"""

    # find the last of the links to new pages
    last_page_link = soup_search.find("div", {"class": "pagination"}).find_all("a")[-1]

    # if the text for that link is Next, grab the link, else end
    if last_page_link.text.strip().startswith("Next") == True:
        next_link = "https://au.indeed.com" + last_page_link.get("href")
    else:
        next_link = "end"

    return next_link


def do_search(url, links_list, count=1):

    """Function finds and returns a list of job pages found in the specified search
    Accepts a search url and a list to collect the links from that search"""

    # including error handling to return result even if next page is not found
    # try:
    original_links = links_list

    # make soup object for url
    soup_search = make_fresh_soup(url)
    count += 1

    # save the links from the soup object
    page_links = get_job_links(soup_search)
    all_links = original_links + page_links

    # find the link to the next page
    next_url = get_next_link(soup_search)

    # repeat with next link until last page located
    if next_url == "end" or len(all_links) > LINK_THRESHOLD:
        print(str(count) + "pages of jobs searched")
        return all_links
    else:
        return do_search(next_url, all_links, count)
    # except:
    #     return links_list


def get_job_details(job_url):

    """Function extracts the job title, company, location, company rating, number of reviews
    job description, and salary from a job listing"""

    # use selenium driver to freeze javascript and capture html
    soup_job = make_fresh_soup(job_url)

    job_details = {}

    # specificed elements are normally present, but adding exception management
    try:
        job_details["job_title"] = soup_job.find("h1", class_="jobsearch-JobInfoHeader-title").text.replace("\n","").strip()
    except:
        job_details["job_title"] = None

    try:
        job_details["company"] = soup_job.find_all("div", class_="icl-u-lg-mr--sm icl-u-xs-mr--xs")[1].text.replace("\n","").strip() #searched, should be the same 
    except:
        job_details["company"] = None

    try:
        job_details["location"] = soup_job.find("div", class_="jobsearch-JobInfoHeader-subtitle").contents[1].text.replace("\n","").strip()
    except:
        job_details["location"] = None

    try:
        job_details["job_description_all_text"] = soup_job.find("div", class_="jobsearch-jobDescriptionText").text.replace("\n","").strip()
    except:
        job_details["job_description_all_text"] = None

    try:
        job_details["salary_data_text"] = soup_job.find("div", id="salaryInfoAndJobType").find("span", class_="attribute_snippet").text.replace("\n","").strip()
    except:
        job_details["salary_data_text"] = None

    try:
        job_details["rating"] = soup_job.find("meta", {"itemprop": "ratingValue"}).attrs["content"]
    except:
        job_details["rating"] = None

    try:
        job_details["reviews"] = soup_job.find("meta", {"itemprop": "ratingCount"}).attrs["content"]
    except:
        job_details["reviews"] = None

    return job_details


def collect_and_save_job_details(job_links, industry, location, filename):

    """Function iterates through a list of links for individual jobs
    Collects the details of each job
    Converts to dataframe and saves to csv"""

# specifying file path 
    file_path = "C:/Users/kilda/OneDrive/THESIS/Scripts/data/" + filename
    jobs = []

    for job in job_links:
        new_job = get_job_details(job)
        jobs.append(new_job)

    jobs_df = pd.DataFrame(jobs)
    jobs_df["industry"] = industry
    jobs_df["search_location"] = location
    jobs_df.to_csv(file_path, index=False, sep=";")


def industry_location_search(industries, locations):

    """Function collects job details from and Indeed search including search terms and location
    industries must be a list of lists of search terms (single terms must be a single list)
    locations must be a list of [city, state] e.g. ['Melbourne', 'VIC']"""

    for industry in industries:

        for location in locations:

            job_links = []

            search_url = indeed_search(industry, location)
            job_links = do_search(search_url, job_links)

            location_string = location[0].lower()
            industry_string = industry[0]
            for term in industry[1:]:
                industry_string = industry_string + term

            filename = industry_string + "_" + location_string + ".csv"

            collect_and_save_job_details(
                job_links, industry_string, location_string, filename
            )


def get_file_names(industries, locations):

    """Function combines previously saved .csv files for a location and industry into one file
    industries and locations need to be from the lists of lists used for searching"""

    filenames = []

    for industry in industries:

        for location in locations:

            location_string = location[0].lower()

            industry_string = industry[0]
            for term in industry[1:]:
                industry_string = industry_string + term

            filename = industry_string + "_" + location_string + ".csv"
            filenames.append(filename)

    return filenames

 # combining all locations, generates a file per location, which can then be concatinated after
 # can add multiple industries 
industries = [['engineer']]
# can add multiple locations 
locations = [['Sydney', 'NSW'], ['Melbourne', 'VIC'], ['Brisbane','QLD'], ['Adelaide','SA'],['Canberra','ACT'], ['Perth','WA'], ['Darwin','NT']]

# run the industry and location search 
f = industry_location_search(industries, locations)



