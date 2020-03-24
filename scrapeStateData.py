import pandas as pd
import yaml
import numpy as np
import ssl
import requests
import urllib
import json
import dpath.util

def getOrDefault(config: object, attr: object, default: object) -> object:
    retValue = default
    if attr in config:
        retValue = config[attr]
    return retValue

def mangleUrl(config: object, url: object) -> object:
    if config['type'] == 'api-json':
        url = url.replace(config['countyDelim'],)
    return ''

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

def scrapeHtmlTable(stateConfig):
    html = getSiteContent(stateConfig['url'])

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

    print(df)
    print(df.columns)

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
        df['Deaths'] = df['Deaths'].str.replace('\u200b', '')
        df['Deaths'].replace('', 0, inplace=True)
        df['Deaths'].fillna(0, inplace=True)

    # Add recovered column if not present
    if 'Recovered' not in df:
        df['Recovered'] = 0
    else:
        df['Recovered'] = df['Recovered'].str.replace('\u200b', '')
        df['Recovered'].replace('', 0, inplace=True)
        df['Recovered'].fillna(0, inplace=True)

    df = df.astype({'Deaths': 'int64', 'Cases': 'int64', 'Recovered': 'int64'})

    # Add state column
    df['State'] = state

    # Reorder columns
    df = df[['County', 'State', 'Cases', 'Deaths', 'Recovered']]

    print(df.describe())
    print(df.dtypes)
    print(df)
    return df

def scrapeApiJson(stateConfig, state):
    df = pd.DataFrame()

    jsonResult = json.loads(getSiteContent(stateConfig['url']))

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

    df = df.astype({'Deaths': 'int64', 'Cases': 'int64', 'Recovered': 'int64'})
    df = df[['County', 'State', 'Cases', 'Deaths', 'Recovered']]

    print(df)
    return df


with open('stateConfig.yml') as configFile:
    pd.set_option('display.max_rows', None)
    configs = yaml.safe_load(configFile)

    aggrDf = pd.DataFrame()
    for state in configs['states']:
        print('DOING STATE', state)
        stateConfig = configs['states'][state]

        df = pd.DataFrame()
        if 'type' not in stateConfig or stateConfig['type'] == 'table':
            df = scrapeHtmlTable(stateConfig)
        elif stateConfig['type'] == 'api-json':
            df = scrapeApiJson(stateConfig, state)