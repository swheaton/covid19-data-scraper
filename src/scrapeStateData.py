import pandas as pd
import yaml
import numpy as np
import ssl
import requests
from requests_html import HTMLSession
import urllib
import json
import dpath.util
import sys
from lxml import html as htmlparse
from io import StringIO
import re

def getOrDefault(config: object, attr: object, default: object) -> object:
    retValue = default
    if attr in config:
        retValue = config[attr]
    return retValue

def getSiteContent(url):
    # Doing this to look more like a browser so we won't get denied.
    header = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    r = None
    content = None
    try:
        r = requests.get(url, headers=header)
        content = r.text
    except requests.exceptions.SSLError:
        print('SSLError, trying to fake SSL context')
        context = ssl._create_unverified_context()
        r = urllib.request.urlopen(url, context=context)
        content = r.read()
    return content

def doJsRender(url, tosleep):
    content = None
    with HTMLSession() as session:
        r = session.get(url)
        r.html.render(timeout=0, sleep=tosleep)
        content = r.html.html
    return content

def scrapeHtmlTable(stateConfig, state, pagecontent):
    html = pagecontent

    tableIndex = getOrDefault(stateConfig, 'tableIndex', 0)
    headerRowsToSkip = getOrDefault(stateConfig, 'headerRowsToSkip', 0)
    df = pd.read_html(html, skiprows=headerRowsToSkip, header=0)[tableIndex]

    # Drop last (total col) if needed
    footerRowsToSkip = getOrDefault(stateConfig, 'footerRowsToSkip', 0)
    if footerRowsToSkip != 0:
        df = df[:-footerRowsToSkip]

    # Zero-width space used by Pennsylvania...
    assert isinstance(df.columns.str, object)
    df.columns = df.columns.str.replace('\u200b', '')

    countyCol = getOrDefault(stateConfig, 'countyCol', 'County')
    casesCol = getOrDefault(stateConfig, 'casesCol', 'Cases')
    columnRename = dict(zip((countyCol, casesCol), ('County', 'Cases')))
    df.rename(columns=columnRename, inplace=True)

    print(df)

    # Extract number if cases col is string.
    #   And also zero-width space first...
    if df['Cases'].dtype == np.object:
        df['Cases'] = df['Cases'].str.replace('\u200b', '')
        df['Cases'] = df['Cases'].str.extract('(?P<Cases>\d*)')

    # Remove all extraneous columns
    df.drop(df.columns.difference(['County', 'Cases', 'Deaths', 'Recovered']), axis=1, inplace=True)

    # Add deaths column if not present
    if 'Deaths' not in df:
        df['Deaths'] = 0
    else:
        df['Deaths'] = df['Deaths']
        if df['Deaths'].dtype == np.object:
            df['Deaths'] = df['Deaths'].str.replace('\u200b', '')
            df['Deaths'].replace('', 0, inplace=True)
            df['Deaths'].replace('-', 0, inplace=True)
        df['Deaths'].fillna(0, inplace=True)

    # Add recovered column if not present
    if 'Recovered' not in df:
        df['Recovered'] = 0
    else:
        df['Recovered'] = df['Recovered']
        if df['Recovered'].dtype == np.object:
            df['Recovered'] = df['Recovered'].str.replace('\u200b', '')
            df['Recovered'].replace('', 0, inplace=True)
            df['Recovered'].replace('-', 0, inplace=True)
        df['Recovered'].fillna(0, inplace=True)

    # Add state column
    df['State'] = state

    return df

def scrapeApiJson(stateConfig, state, pagecontent):
    df = pd.DataFrame()

    jsonResult = json.loads(pagecontent)

    for countyJson in dpath.util.get(jsonResult, stateConfig['countyListDpath']):
        county = dpath.util.get(countyJson, stateConfig['countyDpath'])
        numCases = dpath.util.get(countyJson, stateConfig['casesDpath'])
        numDeaths = dpath.util.get(countyJson, stateConfig['deathsDpath']) if 'deathsDpath' in stateConfig else 0
        numRecovered = dpath.util.get(countyJson, stateConfig['recoveredDpath']) if 'recoveredDpath' in stateConfig else 0
        df = df.append( {
                'County' : county ,
                'State' : state,
                'Cases': numCases or 0,
                'Deaths': numDeaths or 0,
                'Recovered': numRecovered or 0} , ignore_index=True)

    return df

def scrapeText(stateConfig, state, pagecontent):
    tree = htmlparse.fromstring(pagecontent)
    subtree = tree.xpath(stateConfig['dataXpath'])
    dataString = str(htmlparse.tostring(subtree[0]))

    startIndex = 0
    if 'startDelim' in stateConfig:
        startDelim = stateConfig['startDelim']
        startIndex = dataString.find(startDelim) + len(startDelim)
    elif 'firstCounty' in stateConfig:
        startIndex = dataString.find(stateConfig['firstCounty'])
    else:
        print("ERROR: did you mean to not have a start delim or first county?")
    endDelim = stateConfig['endDelim']

    dataString = dataString[startIndex : dataString.find(endDelim)]
    dataList = dataString.split(getOrDefault(stateConfig, 'eltDelim', ','))

    df = pd.DataFrame()
    for countyDatum in dataList:
        countyDatum = countyDatum.strip().replace('(', '').replace(')', '').replace(':', '')
        countyDatum = re.sub(r'<[^>]+>', '', countyDatum)

        dataTuple = countyDatum.split()
        if not dataTuple[-1].isdigit():
            dataTuple.append(0)

        df = df.append({
            'County': ' '.join(dataTuple[0:len(dataTuple)-1]),
            'State': state,
            'Cases': dataTuple[-1] or 0,
            'Deaths': 0, # update to non-zero
            'Recovered': 0}, ignore_index=True) # update to non-zero

    return df

def scrapeCsv(stateConfig, state, pagecontent):
    footerRowsToSkip = getOrDefault(stateConfig, 'footerRowsToSkip', 0)
    df = pd.read_csv(StringIO(pagecontent), skipfooter=footerRowsToSkip)
    countyCol = getOrDefault(stateConfig, 'countyCol', 'County')
    casesCol = getOrDefault(stateConfig, 'casesCol', 'Cases')
    columnRename = dict(zip((countyCol, casesCol), ('County', 'Cases')))
    df.rename(columns=columnRename, inplace=True)
    df['Deaths'] = 0
    df['Recovered'] = 0
    df['State'] = state
    return df

with open('stateConfig.yml') as configFile:
    pd.set_option('display.max_rows', None)
    configs = yaml.safe_load(configFile)

    # if specified on command line, do only those states. otherwise do all
    states = configs['states']
    if len(sys.argv) > 1:
        states = sys.argv[1:]

    # Process each state
    aggrDf = pd.DataFrame()
    for state in states:
        print('DOING STATE', state)
        stateConfig = configs['states'][state]

        if 'doJsRender' in stateConfig and stateConfig['doJsRender']:
            sleepAfterRender = getOrDefault(stateConfig, 'sleepAfterRender', 5)
            pagecontent = doJsRender(stateConfig['url'], sleepAfterRender)
        else:
            pagecontent = getSiteContent(stateConfig['url'])

        if 'type' not in stateConfig or stateConfig['type'] == 'table':
            statedf = scrapeHtmlTable(stateConfig, state, pagecontent)
        elif stateConfig['type'] == 'api-json':
            statedf = scrapeApiJson(stateConfig, state, pagecontent)
        elif stateConfig['type'] == 'text':
            statedf = scrapeText(stateConfig, state, pagecontent)
        elif stateConfig['type'] == 'csv':
            statedf = scrapeCsv(stateConfig, state, pagecontent)
        else:
            statedf = pd.DataFrame()

        statedf = statedf.astype({'Deaths': 'int64', 'Cases': 'int64', 'Recovered': 'int64'})
        statedf = statedf[['County', 'State', 'Cases', 'Deaths', 'Recovered']]

        print(statedf)
        print(statedf.dtypes)
        aggrDf = aggrDf.append(statedf)
    print(aggrDf)
    aggrDf.to_csv('data/out.csv', index=False)
    print("Saved to data/out.csv")
