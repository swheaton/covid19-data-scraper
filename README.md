# COVID19 Data Scraper
A python web scraper utilizing various tools to aggregate up-to-date COVID19 (novel coronavirus 2019) case data. Currently operates at the level of US counties.

For any implemented method below, each state is completely configurable in [yaml](https://pyyaml.org/wiki/PyYAMLDocumentation) _stateConfig.yml_ such that new data sources can be added without code changes.


## Methods
- Scrape HTML ```<table>``` using [requests](https://requests.readthedocs.io/en/master/) module and [pandas](https://pandas.pydata.org/)
- Scrape [JSON](https://docs.python.org/3/library/json.html) return from a web API call. Process in a configurable manner using [dpath](https://pypi.org/project/dpath/)
- HTML text scrape using [lxml](https://lxml.de/) for Xpath search and [regular expressions (re)](https://docs.python.org/3/library/re.html)
- Scrape PDF for table data using [pdftotext](https://www.xpdfreader.com/pdftotext-man.html)
- Scrape image for table data using [Pillow](https://pillow.readthedocs.io/en/stable/) for image manipulation and [pytesseract](https://pypi.org/project/pytesseract/) optical character recognition (OCR) functionality
- Pre-rendering JavaScript on a page using [html-request](https://pypi.org/project/requests-html/)

## Proposed Methods for Remaining States
- Tableau app
- County-level page scraping

## Progress
- 40 / 50 US states
  - :white_check_mark: Alabama
  - :white_check_mark: Alaska
  - :x: American Samoa
  - :x: Arizona
  - :white_check_mark: Arkansas
  - :x: California
  - :x: Colorado
  - :white_check_mark: Connecticut
  - :white_check_mark: Delaware
  - :x: District of Columbia
  - :white_check_mark: Florida
  - :white_check_mark: Georgia
  - :x: Guam
  - :white_check_mark: Hawaii
  - :white_check_mark: Idaho
  - :white_check_mark: Illinois
  - :white_check_mark: Indiana
  - :white_check_mark: Iowa
  - :white_check_mark: Kansas
  - :x: Kentucky
  - :white_check_mark: Lousiana
  - :white_check_mark: Maine
  - :x: Marshall Islands
  - :white_check_mark: Maryland
  - :white_check_mark: Massachusetts
  - :white_check_mark: Michigan
  - :x: Micronesia
  - :white_check_mark: Minnesota
  - :white_check_mark: Mississippi
  - :white_check_mark: Missouri
  - :white_check_mark: Montana
  - :x: Nebraska
  - :x: Nevada
  - :x: New Hampshire
  - :white_check_mark: New Jersey
  - :white_check_mark: New Mexico
  - :white_check_mark: New York
  - :white_check_mark: North Carolina
  - :white_check_mark: North Dakota
  - :x: Northern Mariana Islands
  - :x: Ohio
  - :white_check_mark: Oklahoma
  - :white_check_mark: Oregon
  - :white_check_mark: Pennsylvania
  - :x: Puerto Rico
  - :x: Republic of Palau
  - :white_check_mark: Rhode Island
  - :white_check_mark: South Carolina
  - :white_check_mark: South Dakota
  - :white_check_mark: Tennessee
  - :white_check_mark: Texas
  - :x: US Virgin Islands
  - :white_check_mark: Utah
  - :x: Vermont
  - :x: Virginia
  - :white_check_mark: Washington
  - :white_check_mark: West Virginia
  - :white_check_mark: Wisconsin
  - :white_check_mark: Wyoming
- 0 / 9 districts, territories, and freely associated states

## Noteable Python Modules Used
- pandas
- yaml
- numpy
- ssl
- requests
- urllib
- json
- dpath.util
- lxml
- pdftotext (system utility, not python module of same name)

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
