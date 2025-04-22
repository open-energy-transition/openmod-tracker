
#
# Update package history based on latest available statistics from ecosyste.ms and anaconda
#
# (C) Open Energy Transition (OET)
# License: MIT / CC0 1.0
#

# import required packages
import requests
from datetime import datetime, timedelta
from pandas import DataFrame
from streamlit import html, title, write, set_page_config
from itables.streamlit import interactive_table

# define the path of the CSV file listing the packages to assess
url_api = 'https://ost.ecosyste.ms/api/v1/projects/esd'

# use the screen in wide format
set_page_config(layout="wide")

# define variables
names = []
urls = []
descriptions = []
categories = []
sub_categories = []
languages = []
licenses = []
download_counts = []
total_dependent_repos_counts = []
stars = []
citations = []
forks = []
contributors = []
develop_distr_scores = []
past_year_issues_counts = []
creates = []
updates = []

# get the JSON file from the ost.ecosyste.ms
json_url = url_api
r = requests.get(json_url)
all_data = r.json()

# loop through the JSON file just received
for i in range(len(all_data)):
    json_data = all_data[i]
    package_downloads = 0
    dependent_repos_count = 0
    latest_release_published_at = None
    for package_manager in range(len(json_data['packages'])):
        if json_data['packages'][package_manager]['downloads']:
                if json_data['packages'][package_manager]['downloads_period'] == "last-month":
                    package_downloads += json_data['packages'][package_manager]['downloads']

        if json_data['packages'][package_manager]['dependent_repos_count']:
                dependent_repos_count += json_data['packages'][package_manager]['dependent_repos_count']

        if latest_release_published_at is None or latest_release_published_at < json_data['packages'][package_manager]['latest_release_published_at']:
            latest_release_published_at = json_data['packages'][package_manager]['latest_release_published_at']

    if package_downloads:
        download_counts.append(package_downloads)
    else:
        download_counts.append(0)

    # store necessary details
    names.append(json_data['name'])
    urls.append(json_data['url'])
    descriptions.append(json_data['description'])
    categories.append(json_data['category'])
    sub_categories.append(json_data['sub_category'])
    languages.append(json_data['language'])
    licenses.append(json_data['repository']['license'])
    total_dependent_repos_counts.append(dependent_repos_count)
    stars.append(json_data['repository']['stargazers_count'])
    citations.append(json_data['total_citations'])
    forks.append(json_data['repository']['forks_count'])
    contributors.append(json_data['repository']['commit_stats']['total_committers'])
    develop_distr_scores.append(("%.3f" % json_data['commits']['dds']))
    past_year_issues_counts.append(json_data['issues_stats']['past_year_issues_count'])
    creates.append(datetime.strptime(json_data['repository']['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y/%m'))
    updates.append(datetime.strptime(latest_release_published_at, '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y/%m'))

# create a dataframe containing all collected data
df = DataFrame()
df['Project Name'] = names
df['Project Name'] = names
df['Category'] = categories
df['Sub Category'] = sub_categories
df['Created'] = creates
df['Updated'] = updates
df['License'] = licenses
df['Language'] = languages
df['Citations'] = citations
df['Stars'] = stars
df['Contribs'] = contributors
df['DDS'] = develop_distr_scores
df['Forks'] = forks
df['Dependents'] = total_dependent_repos_counts
df['PM Downloads'] = download_counts
df['PY Issues']= past_year_issues_counts

# adjust some license details
df.loc[df['Project Name'] == 'Antares Simulator', 'License'] = 'mpl-2.0'
df.loc[df['Project Name'] == 'FINE', 'License'] = 'mit'
df.loc[df['Project Name'] == 'Minpower', 'License'] = 'mit'
df.loc[df['Project Name'] == 'pandapower', 'License'] = 'bsd-3-clause'
df.loc[df['Project Name'] == 'switch-model', 'License'] = 'apache-2.0'
df.loc[df['Project Name'] == 'Temoa', 'Language'] = 'Python'
df.loc[df['Project Name'] == 'PyPowSyBl', 'Language'] = 'Python'

# delete some columns not needed yet
df.drop(columns=[
    'Category', 'Sub Category', 'Language', 'License'
], axis=1, errors='ignore', inplace=True)

# start the output
title("OET's ESD analysis app")
write("")
write("Repository to support analyzing Energy System Modelling (ESM) tools based on git data and other publicilly available data (e.g., ecosyste.ms and opensustain.tech).")
write("The whole analysis is available at OET's GitHub repository [github.com/open-energy-transition/open-esm-analysis](https://github.com/open-energy-transition/open-esm-analysis/).")
write("")

# add the interactive table
interactive_table(
    df,
    # caption='Countries',
    #select=True,
    lengthMenu=[25, 50],
    buttons=['copyHtml5', 'csvHtml5', 'excelHtml5', 'colvis'],
    order=[[0, "asc"]]
)

# add some comments about some columns
write ("")
write ("Remark:")
write ("  Contribs .. contributors")
write ("  DDS ... development distribution score (the smaller the number the better; 0 means no data available)")
write ("  PM .. previous month (0 means either no downloads or not tracked/shared from the repository owner)")
write ("  PY .. previous year (0 means either no issues or not tracked/shared from the repository owner)")
write ("")
