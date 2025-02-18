#
# Update package history based on latest available statistics from ecosyste.ms and anaconda
#
# (C) Open Energy Transition (OET)
# Distributed via MIT license
#

import os.path
import json
import io
from datetime import datetime, timedelta
import requests
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import openpyxl
import pyarrow

# define necessary pathes towards ecosyste.ms
URL_projects = "https://ost.ecosyste.ms/api/v1/projects"
URL_packages = "https://ost.ecosyste.ms/api/v1/projects/packages"

FILE_TO_SAVE_AS = "ecosystems_packages.json" # the name you want to save file as

# define necessary path towards anaconda (latest available parquet file via S3
# s3_path = 's3://anaconda-package-data/conda/monthly/2025/2025-01.parquet'
input_dt = datetime(datetime.today().year, datetime.today().month, datetime.today().day)
first = input_dt.replace(day=1)
res = first - timedelta(days=1)
s3_path = 's3://anaconda-package-data/conda/monthly/'+res.date().strftime('%Y')+'/'+res.date().strftime('%Y-%m')+'.parquet'

# define some required packages
def get_julia_pkg_downloads(package_name):
    """
    Fetch the monthly download statistics for a Julia package by name.

    Args:
        package_name (str): The name of the Julia package.

    Returns:
        dict: A dictionary containing download statistics or an error message.
    """
    try:
        # Define the URL for the Julia package statistics API
        url = f"https://juliapkgstats.com/api/v1/monthly_downloads/{package_name}"

        # Make the GET request
        response = requests.get(url)

        # Raise an exception for HTTP errors
        response.raise_for_status()

        # Parse the JSON response
        data = response.json()

        return {
            "package": package_name,
            "monthly_downloads": data.get("total_requests", "Data not available"),
            "details": data
        }

    except requests.exceptions.HTTPError as http_err:
        return {"error": f"HTTP error occurred: {http_err}"}
    except requests.exceptions.RequestException as req_err:
        return {"error": f"Request error occurred: {req_err}"}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

def get_ost_detail(OST_URL, FILE_TO_SAVE_AS):
    resp = requests.get(OST_URL) # requesting the projects from OST server

    with open(FILE_TO_SAVE_AS, "wb") as f: # opening a file handler to create new file
        f.write(resp.content) # writing content to file

    return (f)

def get_datatable(FILE_TO_READ_FROM):
    with open(FILE_TO_READ_FROM, 'r', encoding='utf-8') as f:
        content = f.read()
        f.close()

    return (content)

# Create a Plotly table
def plot_dataframe_as_table(df):
    """
    Create a Plotly table from a pandas DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame to visualize.

    Returns:
        Plotly figure
    """
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(df.columns),
            fill_color='lightblue',
            align='center',
            font=dict(color='black', size=14)
        ),
        cells=dict(
            values=[df[col] for col in df.columns],
            fill_color='lightgrey',
            align='center',
            font=dict(color='black', size=12)
        )
    )])
    fig.update_layout(title="Usage of Open Source Projects in Energy Modelling - January 2025", margin=dict(l=0, r=0, t=30, b=0))
    fig.show()

if os.path.isfile(FILE_TO_SAVE_AS+'3.parque'):
    # read from downloaded files
    print ('Read the available local files ...')
    df_conda = pd.read_parquet(FILE_TO_SAVE_AS+'3.parque')

else:
    # download all data
    print ('Download the data from the individual servers ...')
    resp = get_ost_detail(URL_packages, FILE_TO_SAVE_AS+'1.json') # requests the packages from OST server
    resp = get_ost_detail(URL_projects, FILE_TO_SAVE_AS+'2.json') # requests the packages from OST server
    df_conda = pd.read_parquet(s3_path, engine='pyarrow') # Load the Parquet file into a DataFrame
    df_conda.to_parquet(FILE_TO_SAVE_AS+'3.parque')

df_packages = pd.read_json(io.StringIO(get_datatable(FILE_TO_SAVE_AS+'1.json')))
df_projects = pd.read_json(io.StringIO(get_datatable(FILE_TO_SAVE_AS+'2.json')))

print ('Necessary data now are available.')

names = []
url = []
description = []
category = []
sub_category = []
language = []
license = []
download_counts = []
total_dependent_repos_count = []
stars = []
doi = []
citations = []
forks = []
contributors = []
develop_distr_score = []
share_top_contributor = []
past_year_issues_count = []
created = []
updated = []

for index, row in df_packages.iterrows():
    name = row['name']
    if row['packages'][0]['namespace'] != None:
        owner = row['packages'][0]['namespace'][11:]
        repro = row['packages'][0]['repository_url'][len(row['packages'][0]['namespace'])+len('https://')+1:]
    else:
        owner = ''
        repro = ''

    package_downloads = 0
    dependent_repos_count = 0
    for package_manager in range(len(row['packages'])):
        if row['packages'][package_manager]['downloads']:
                if row['packages'][package_manager]['downloads_period'] == "last-month":
                    package_downloads += row['packages'][package_manager]['downloads']

        if row['packages'][package_manager]['dependent_repos_count']:
                dependent_repos_count += row['packages'][package_manager]['dependent_repos_count']

    if row['language'] == "Python":
        conda_downloads = df_conda[df_conda['pkg_name'] == row['name']]['counts'].sum()
        package_downloads += conda_downloads

    try:
        download_counts.append(package_downloads)
    except:
        download_counts.append(0)

    try:
        contributors.append(row['repository']['commit_stats']['total_committers'])
    except:
        contributors.append(0)

    names.append(name)
    stars.append(row['repository']['stargazers_count'])
    past_year_issues_count.append(row['issues_stats']['past_year_issues_count'])
    url.append(row['url'])
    description.append(row['description'])
    category.append(row['category'])
    sub_category.append(row['sub_category'])
    language.append(row['language'])
    license.append(row['repository']['license'])
    citations.append(row['total_citations'])
    forks.append(row['repository']['forks_count'])
    created.append(datetime.strptime(row['repository']['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y/%m'))
    updated.append(datetime.strptime(row['repository']['updated_at'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y/%m'))
    total_dependent_repos_count.append(dependent_repos_count)
    develop_distr_score.append(row['commits']['dds'])

df_extract = pd.DataFrame()
df_extract['Project Name'] = names
df_extract['Project Name'] = names
df_extract['Category'] = category
df_extract['Sub Category'] = sub_category
df_extract['Created'] = created
df_extract['Updated'] = updated
df_extract['License'] = license
df_extract['Language'] = language
df_extract['Citations'] = citations
df_extract['Stars'] = stars
df_extract['Contributors'] = contributors
df_extract['DDS'] = develop_distr_score
df_extract['Forks'] = forks
df_extract['Dependents'] = total_dependent_repos_count
df_extract['PM Downloads'] = download_counts
df_extract['PY Issues']= past_year_issues_count

# This project are lost between OpenSustain.tech and this script: OSeMOSYS, times_model, SpineOpt.jl
df_extract = df_extract[df_extract['Project Name'].isin(
    ['Antares Simulator', 'AnyMOD.jl', 'balmorel', 'Calliope', 'FINE', 'GenX', 'GridPath', 'NemoMod.jl',
     'Minpower', 'oemof-solph', 'openTEPES', 'OSeMOSYS', 'pandapower', 'powersimulationsdynamics.jl',
     'PowerSystems.jl',
     #'PowSyBl Open Load Flow',
     'PyPowSyBl', 'PyPSA', 'pypsa-earth', 'Sienna', 'SpineOpt.jl',
     'switch-model', 'Temoa', 'TulipaEnergyModel.jl', 'times_model'])]

# walk through Julia packages as typically they are named without the ".jl" at the end
for index, row in df_extract[df_extract['Language'] == 'Julia'].iterrows():
    try:
        if row['Project Name'][-3:] == '.jl':
            df_extract.loc[df_extract["Project Name"] == row['Project Name'], "PM Downloads"] = \
                int(get_julia_pkg_downloads(row['Project Name'][0:-3])['monthly_downloads'])
        else:
            df_extract.loc[df_extract["Project Name"] == row['Project Name'], "PM Downloads"] = \
                int(get_julia_pkg_downloads(row['Project Name'])['monthly_downloads'])
    except:
        df_extract.loc[df_extract["Project Name"] == row['Project Name'], "PM Downloads"] = 0

## The following projects can not be evaluated since two different API from ecosyste.ms are needed.
## This is simpilfied in future versions. For now the data is hardcoded here for the 17.01.2025
new_projects = pd.DataFrame([
    {   'Project Name': 'OSeMOSYS',
        'Stars': 163,
        'Citations': 568,
        'PM Downloads': 0,
        'Dependents': 0,
        'License': 'apache-2.0',
        'Language': 'Python',
        'PY Issues': 45,
        'Contributors': 11,
        'Forks': 104,
        'Created': '2016/10',
        'Updated': '2023/06',
        'DDS': 0,
    },
    {   'Project Name': 'times_model',
        'Stars': 116,
        'Citations': 0,
        'PM Downloads': 0,
        'Dependents': 0,
        'License': 'gpl-3.0',
        'Language': 'GAMS',
        'PY Issues': 0,
        'Contributors': 3,
        'Forks': 40,
        # creation not clearly indicated
        # guess based on https://iea-etsap.org/docs/Documentation_for_the_TIMES_Model-Part-I_July-2016.pdf
        'Created': '1990/07',
        'Updated': '2025/01',
        'DDS': 0,
    },
    {   'Project Name': 'Dispa-SET',
        'Stars': 86,
        'Citations': 0,
        'PM Downloads': 0,
        'Dependents': 0,
        'License': 'eupl-1.2',
        'Language': 'GAMS',
        'PY Issues': 16,
        'Contributors': 13,
        'Forks': 39,
        'Created': '2018/10',
        'Updated': '2024/04',
        'DDS': 0,
    }
])

# Append new data to the DataFrame
df_extract = pd.concat([df_extract, new_projects], ignore_index=True)

# how to enter data into the official repository?
df_extract.loc[df_extract.index[df_extract['Project Name'] == 'Antares Simulator'].values[0], 'License'] = 'mpl-2.0'
df_extract.loc[df_extract.index[df_extract['Project Name'] == 'FINE'].values[0], 'License'] = 'mit'
df_extract.loc[df_extract.index[df_extract['Project Name'] == 'Minpower'].values[0], 'License'] = 'mit'
df_extract.loc[df_extract.index[df_extract['Project Name'] == 'pandapower'].values[0], 'License'] = 'bsd-3-clause'
df_extract.loc[df_extract.index[df_extract['Project Name'] == 'switch-model'].values[0], 'License'] = 'apache-2.0'
df_extract.loc[df_extract.index[df_extract['Project Name'] == 'Temoa'].values[0], 'Language'] = 'Python'
df_extract.loc[df_extract.index[df_extract['Project Name'] == 'PyPowSyBl'].values[0], 'Language'] = 'Python'

df_extract.drop(columns=['Category', 'License', 'Sub Category', 'Owner', 'Repository', 'Language'], axis=1, errors='ignore', inplace=True)

df_extract.style.format({
    'Citations':'{:,.0f}',
    'Stars':'{:,.0f}',
    'DDS':'{:,.2f}',
    'PM Downloads':'{:,.0f}',
    'PY Issues':'{:,.0f}'
})

print (df_extract)
