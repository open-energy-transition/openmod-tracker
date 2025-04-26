
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
from streamlit import html, title, write, set_page_config, subheader, page_link, markdown
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
title ("OET's open-source tool adaption tracker")
write ()
write ("Repository to support analyzing Energy System Modelling (ESM) tools based on git data and other publicilly available data (e.g., <a href='https://ecosyste.ms/' target='_new'>ecosyste.ms</a> and <a href='https://opensustain.tech/' target='_new'>opensustain.tech</a>.", unsafe_allow_html=True)
write ("The whole analysis is available at OET's GitHub repository <a href='https://github.com/open-energy-transition/open-esm-analysis/' target='_new'>open-esm-analysis</a>.", unsafe_allow_html=True)
subheader ("Smarter Investments in Open Energy Planning: How Data Can Guide Decision-Makers")
markdown ("The global energy transition is moving fast, but so are the challenges in directing time and resources effectively. Achieving international climate goals will require around **4.5 trillion in annual investments** by the early 2030s. To optimize infrastructure investments, grid operations and policy decisions, open-source tools are becoming the 'goat' in the room with increasing adoption across all sectors (see e.g. <a href='https://www.linkedin.com/posts/entso-e_energytransition-opensource-innovation-activity-7293296246813851649-2ynL?utm_source=share&utm_medium=member_desktop&rcm=ACoAAB8VqvQBiD-xO3KcGAhxNnzGWGUnox2Mxb8'>ENTSO-E post on LinkedIn</a>).", unsafe_allow_html=True)
markdown ("But with an ever-growing number of open-source (OS) energy tools, the question remains: **How do decision-makers - whether researchers, funders, or grid operators - select the right tools for their needs?** The answer lies in data combined with experience.")
subheader ("The Challenge: Identifying Reliable and Impactful Tools")
write ("Funders and users alike need to distinguish between active, well-maintained tools and those that might no longer be viable. While qualitative reviews (user feedback, case studies, etc.) are valuable, quantitative metrics offer critical signals about a tool’s reliability, sustainability, and adoption.")
markdown ("**Table 1** highlights key statistics for several leading OS energy planning tools, offering a snapshot of their development activity, usage, and maintenance.")
write ("")
markdown ("**Table 1: Selected Open-Source ESM Tools - Key Data Indicators** (Data: ecosystem.ms; Last Update: " + datetime.now().strftime("%d. %b. %Y") + ")")

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
markdown ("*(Citations: Papers referencing the tool; Created: first repository commit; Updated: last repository commit; Citations: identified publications; Stars: GitHub bookmarks; Contributors: active developers; DDS: development distribution score (the smaller the number the better; but 0 means no data available); Forks: number of Git forks; Dependents: packages dependent on this project; PM Downloads: package installs; PY Issues: bugs reported in the past year.)*")
write ("")
subheader ("Key Takeaways from the Data")
markdown ("- **Adoption Signals Matter**: High download counts, active contributors, and ongoing issue resolutions suggest healthy, well-maintained projects. However, GitHub stars alone can be misleading—some highly starred projects have stalled development.")
markdown ("- **Sustainability Risks**: Projects with fewer than 10 contributors face a higher risk of abandonment. Also depending on packages with a small number of contributors might be a risk for the project. Funders should be wary of investing in tools that lack a committed maintainer base.")
markdown ("- **Transparency Gaps**: Some projects do not disclose key statistics (e.g., download counts), which may indicate poor release management and hinder long-term usability.")
markdown ("- **Interoperability Potential**: Many tools serve niche roles, but interoperability—how well they integrate with others—is becoming a crucial factor for large-scale adoption.")
write ("")
subheader("Beyond Data: The Need for Qualitative Assessments")
write ("While data helps filter out unreliable tools, deeper investigation is needed to ensure a tool is the right fit. Some key qualitative factors to consider:")
markdown ("- **Documentation Quality**: Are installation and usage guides clear and up to date?")
markdown ("- **Community Support**: Is there an active forum, mailing list, or issue tracker?")
markdown ("- **Use Cases**: Has the tool been applied in real-world projects similar to your needs?")
markdown ("- **Licensing & Governance**: Is it permissively licensed (e.g., MIT) or does it enforce restrictions (e.g., GPL)?")
markdown ("- **Collaboration Potential**: Can multiple stakeholders contribute effectively?")
write ("")
subheader("The Case for a Live Decision-Support Platform")
write ("Right now, there is no single source of truth for assessing the viability of open-source energy planning tools. An up-to-date, data-driven decision-support platform could bridge this gap, providing real-time insights on:")
markdown ("- **Maintenance health** (contributor activity, unresolved issues)")
markdown ("- **Adoption rates** (downloads, citations, user engagement)")
markdown ("- **Tool interoperability** (compatibility testing with other OS models)")
markdown ("- **Funding needs** (identifying tools at risk due to lack of maintainers)")

write ("")
write ("Such a platform would empower funders to invest wisely, helping direct resources to projects with the highest impact potential.")
write ("")
subheader("Conclusion")
write ("Selecting the right OS energy planning tool is no longer just a technical choice — it’s an **investment decision**. While **data-driven insights can highlight adoption trends, sustainability risks, and tool maturity**, *qualitative assessments remain essential for selecting the best fit*.")
markdown ("**By combining live data tracking with structured qualitative evaluation**, the energy community can reduce wasted investments and ensure the best tools remain available for researchers, grid operators, project developers, investors and policymakers.")
markdown ("**Would you find a real-time OS tool insight platform useful?** Share your thoughts and suggestions in the comments or the <a href='https://github.com/open-energy-transition/open-esm-analysis/issues'>issues tracker</a>!", unsafe_allow_html=True)
write ("")
