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
