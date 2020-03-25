# COVID19 Data Scraper
A python web scraper utilizing various tools to aggregate up-to-date COVID19 (novel coronavirus 2019) case data. Currently operates at the level of US counties.

For any implemented method below, each state is completely configurable in [yaml](https://pyyaml.org/wiki/PyYAMLDocumentation) _stateConfig.yml_ such that new data sources can be added without code changes.


## Methods
- Scrape HTML ```<table>``` using [requests](https://requests.readthedocs.io/en/master/) module and [pandas](https://pandas.pydata.org/)
- Scrape [JSON](https://docs.python.org/3/library/json.html) return from a web API call. Process in a configurable manner using [dpath](https://pypi.org/project/dpath/)

## Proposed Methods for Remaining States
- HTML text scrape
- JS render required first
- PDF scrape
- Tableau app
- County-level page scraping

## Progress
- 32 / 50 US states
- 0 / 9 districts, territories, and freely associated states

## Python Modules Used
- pandas
- yaml
- numpy
- ssl
- requests
- urllib
- json
- dpath.util

## TODO
- Expand coverage internationally
- Aggregate time-series data
- Schedule automated run
- Better death count
- Scrape historical data (wayback machine or other methods)
- Individual case level data
- Confirm data with official reports using NLP or other text processing approaches

## Terms of Use
This GitHub repo and its contents herein, including all data, code, mapping, and analysis, copyright 2020 Stuart Wheaton, all rights reserved, is provided to the public strictly for educational and academic research purposes. The Website relies upon publicly available data from multiple sources, that do not always agree. I hereby disclaims any and all representations and warranties with respect to the Website, including accuracy, fitness for use, and merchantability. Reliance on the Website for medical guidance or use of the Website in commerce is strictly prohibited.
