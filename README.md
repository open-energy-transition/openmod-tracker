
Repository to support analyzing Energy System Design (ESD) models based on git data and other publicilly available data (e.g., ecosyste.ms and opensustain.tech).



# Smarter Investments in Open Energy Planning: How Data Can Guide Decision-Makers

The global energy transition is moving fast, but so are the challenges in directing time and resources effectively. Achieving international climate goals will require around **4.5 trillion in annual investments** by the early 2030s. To optimize infrastructure investments, grid operations and policy decisions, open-source tools are becoming the “goat” in the room with increasing adoption across all sectors (ref to [ENTSO-E](https://www.linkedin.com/posts/entso-e_energytransition-opensource-innovation-activity-7293296246813851649-2ynL?utm_source=share&utm_medium=member_desktop&rcm=ACoAAB8VqvQBiD-xO3KcGAhxNnzGWGUnox2Mxb8).

But with an ever-growing number of open-source (OS) energy tools, the question remains: **How do decision-makers—whether researchers, funders, or grid operators—select the right tools for their needs?** The answer lies in data combined with experience.

## The Challenge: Identifying Reliable and Impactful Tools
Funders and users alike need to distinguish between active, well-maintained tools and those that might no longer be viable. While qualitative reviews (user feedback, case studies, etc.) are valuable, **quantitative metrics** offer critical signals about a tool’s reliability, sustainability, and adoption.

The table below highlights key statistics for several leading OS energy planning tools, offering a snapshot of their development activity, usage, and maintenance.

**Table 1: Open-Source Energy Planning Tools - Key Data Indicators**
| Project Name         | Created | Updated | Citations | Stars | Contributors | DDS   | Forks | Dependents | PM Downloads | PY Issues | 
| -------------------- | ------- | ------- | --------- | ----- | ------------ | ----- | ----- | ---------- | ------------ | --------- |
| Antares Simulator    | 2018/07 | 2024/10 |         0 |    58 |           32 | 0.511 |    24 |          0 |            0 |        83 | 
| AnyMOD.jl            | 2019/09 | 2024/09 |         0 |    70 |            4 | 0.190 |    21 |          0 |            6 |         0 | 
| Calliope             | 2013/09 | 2024/10 |       123 |   299 |           22 | 0.393 |    93 |          5 |          672 |        93 | 
| Dispa-SET            | 2018/10 | 2024/04 |         0 |    86 |           13 | 0     |    39 |          0 |            0 |        16 | 
| FINE                 | 2018/07 | 2025/01 |         0 |    73 |           48 | 0.791 |    43 |          2 |         1167 |         9 | 
| GenX                 | 2021/05 | 2025/02 |         0 |   287 |           32 | 0.694 |   126 |          0 |           22 |        88 | 
| GridPath             | 2016/08 | 2024/10 |         0 |    95 |           12 | 0.215 |    36 |          0 |          560 |        12 | 
| Minpower             | 2011/04 | 2024/04 |         0 |    71 |            1 | 0     |    33 |          2 |          782 |         1 | 
| oemof-solph          | 2015/11 | 2024/10 |       175 |   302 |           72 | 0.708 |   126 |         23 |         3792 |        54 | 
| openTEPES            | 2020/07 | 2024/10 |         7 |    39 |            8 | 0.417 |    23 |          1 |         2444 |         9 | 
| OSeMOSYS             | 2016/10 | 2023/06 |       568 |   163 |           11 | 0     |   104 |          0 |            0 |        45 | 
| pandapower           | 2017/01 | 2024/10 |         0 |   863 |          156 | 0.821 |   481 |         75 |        30789 |       120 | 
| PowerSystems.jl      | 2017/12 | 2024/10 |        15 |   308 |           42 | 0.505 |    79 |          0 |          178 |       138 | 
| PyPowSyBl            | 2020/11 | 2024/10 |         0 |    56 |           30 | 0.699 |    12 |          1 |        10378 |        53 | 
| PyPSA                | 2016/01 | 2024/10 |       238 |  1239 |           92 | 0.808 |   454 |         46 |        10602 |        94 | 
| SpineOpt.jl          | 2018/10 | 2024/10 |         0 |    56 |           38 | 0.744 |    13 |          0 |           20 |        99 | 
| switch-model         | 2015/04 | 2025/01 |         0 |   138 |           16 | 0.405 |    85 |          0 |            0 |         0 | 
| Temoa                | 2015/01 | 2024/09 |         0 |    81 |           25 | 0.710 |    49 |          0 |            0 |         2 | 
| times_model          | 1990/07 | 2025/01 |         0 |   116 |            3 | 0     |    40 |          0 |            0 |         0 | 
| TulipaEnergyModel.jl | 2023/08 | 2024/11 |         0 |    27 |           15 | 0.641 |    20 |          0 |           16 |       340 | 

*(Citations: Papers referencing the tool; Created: first repository commit; Updated: last repository commit; Citations: identified publications; Stars: GitHub bookmarks; Contributors: active developers; DDS: development distribution score (the smaller the number the better; but 0 means no data available); Forks: number of Git forks; Dependents: packages dependent on this project; PM Downloads: package installs; PY Issues: bugs reported in the past year.)*

## Key Takeaways from the Data
+ **Adoption Signals Matter**: High download counts, active contributors, and ongoing issue resolutions suggest healthy, well-maintained projects. However, GitHub stars alone can be misleading—some highly starred projects have stalled development.
+ **Sustainability Risks**: Projects with fewer than 10 contributors face a higher risk of abandonment. Also depending on packages with a small number of contributors might be a risk for the project. Funders should be wary of investing in tools that lack a committed maintainer base.
+ **Transparency Gaps**: Some projects do not disclose key statistics (e.g., download counts), which may indicate poor release management and hinder long-term usability.
+ **Interoperability Potential**: Many tools serve niche roles, but interoperability—how well they integrate with others—is becoming a crucial factor for large-scale adoption.

## Beyond Data: The Need for Qualitative Assessments
While **data helps filter out unreliable tools**, deeper investigation is needed to ensure a tool is the right fit. Some key qualitative factors to consider:

+ **Documentation Quality**: Are installation and usage guides clear and up to date?
+ **Community Support**: Is there an active forum, mailing list, or issue tracker?
+ **Use Cases**: Has the tool been applied in real-world projects similar to your needs?
+ **Licensing & Governance**: Is it permissively licensed (e.g., MIT) or does it enforce restrictions (e.g., GPL)?
+ **Collaboration Potential**: Can multiple stakeholders contribute effectively?

## The Case for a Live Decision-Support Platform
Right now, there is **no single source of truth** for assessing the viability of open-source energy planning tools. An **up-to-date, data-driven decision-support platform** could bridge this gap, providing real-time insights on:

+ **Maintenance health** (contributor activity, unresolved issues)
+ **Adoption rates** (downloads, citations, user engagement)
+ **Tool interoperability** (compatibility testing with other OS models)
+ **Funding needs** (identifying tools at risk due to lack of maintainers)

Such a platform would **empower funders to invest wisely**, helping direct resources to projects with the highest impact potential.

## Conclusion
Selecting the right OS energy planning tool is no longer just a technical choice — it’s an **investment decision**. While **data-driven insights can highlight adoption trends, sustainability risks, and tool maturity**, <ins>qualitative assessments remain essential for selecting the best fit</ins>.

By **combining live data tracking with structured qualitative evaluation**, the energy community can reduce wasted investments and ensure the best tools remain available for researchers, grid operators, project developers, investors and policymakers.

Would you find a **real-time OS tool insight platform** useful? Share your thoughts and suggestions in the comments or the issues tracker!
