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
from datetime import datetime, timedelta
import os
from PIL import Image
import pytesseract

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
        content = r.content
    except requests.exceptions.SSLError:
        print('SSLError, trying to fake SSL context')
        context = ssl._create_unverified_context()
        r = urllib.request.urlopen(url, context=context)
        content = r.read()
    return content


def mangleDateInUrl(stateConfig):
    date = datetime.today()# - timedelta(days=1)
    zeroPad = getOrDefault(stateConfig, 'zeroPad', 'none')
    if zeroPad == 'none':
        outDate = date.strftime(stateConfig['dateFormat'])
    elif zeroPad == 'first':
        tokens = stateConfig['dateFormat'].split('%')
        outDate = tokens[0] + date.strftime('%'+tokens[1]).lstrip('0') + date.strftime('%' + '%'.join(tokens[2:]))
    elif zeroPad == 'all':
        tokens = stateConfig['dateFormat'].split('%')
        outDate = tokens[0]
        tokens = tokens[1:]
        for token in tokens:
            outDate = outDate + date.strftime('%'+token).lstrip('0')

    if getOrDefault(stateConfig, 'toLower', False):
        outDate = outDate.lower()
    mangledUrl = stateConfig['url'].replace('{{INSERT_DATE}}', outDate)
    print(mangledUrl)
    return mangledUrl


def doJsRender(url, tosleep):
    content = None
    with HTMLSession() as session:
        r = session.get(url)
        r.html.render(retries=5, timeout=0, sleep=tosleep)
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
    deathsCol = getOrDefault(stateConfig, 'deathsCol', 'Deaths')
    recoveredCol = getOrDefault(stateConfig, 'recoveredCol', 'Recovered')
    columnRename = dict(zip((countyCol, casesCol, deathsCol, recoveredCol), ('County', 'Cases', 'Deaths', 'Recovered')))
    df.rename(columns=columnRename, inplace=True)

    df = df[df['County'].notnull()]
    print(df)

    # Extract number if cases col is string.
    #   And also zero-width space first...
    if df['Cases'].dtype == np.object:
        df['Cases'] = df['Cases'].str.replace('\u200b', '')
        df['Cases'] = df['Cases'].str.replace('<5', getOrDefault(stateConfig, 'replaceLess5', '1'))
        df['Cases'] = df['Cases'].str.extract('(?P<Cases>\d*)')

    print(df)
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
            df['Deaths'].replace(b'\xe2\x80\x94'.decode('utf-8'), 0, inplace=True)
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

        if getOrDefault(stateConfig, 'ignoreStateAsCounty', False) and county == state:
            continue
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
    sentinel = stateConfig['sentinel']

    dataString = dataString[startIndex : dataString.find(sentinel)]
    dataList = dataString.split(getOrDefault(stateConfig, 'eltDelim', ','))

    df = pd.DataFrame()
    for countyDatum in dataList:
        countyDatum = countyDatum.strip().replace('(', '').replace(')', '').replace(':', '')
        countyDatum = re.sub(r'<[^>]+>', '', countyDatum)

        dataTuple = countyDatum.split()
        newInParen = getOrDefault(stateConfig, 'newInParen', False)
        caseIndex = 1
        if newInParen:
            caseIndex = 2
        if not dataTuple[-1].isdigit():
            dataTuple.append(0)

        df = df.append({
            'County': ' '.join(dataTuple[0:len(dataTuple)-caseIndex]),
            'State': state,
            'Cases': dataTuple[-caseIndex] or 0,
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


def scrapePdf(stateConfig, state, pagecontent):
    with open('_tmp/tmp.pdf', 'wb') as pdfFile:
        pdfFile.write(pagecontent)
    try:
        os.remove('_tmp/tmp.txt')
    except FileNotFoundError:
        pass

    pageOfTable = ''
    if 'pageOfTable' in stateConfig:
        pageOfTable = '-f ' + str(stateConfig['pageOfTable']) + ' -l ' + str(stateConfig['pageOfTable'])
    os.system('pdftotext ' + pageOfTable +' -layout _tmp/tmp.pdf')
    df = pd.DataFrame()

    with open('_tmp/tmp.txt', 'r', encoding = "ISO-8859-1") as txtFile:
        lines = txtFile.readlines()
        recording = False
        countyCol = getOrDefault(stateConfig, 'countyCol', 'County')
        casesCol = getOrDefault(stateConfig, 'casesCol', 'Cases')

        headerMatcher = re.compile('\s*'+countyCol+'\s*'+casesCol)
        for line in lines:
            line = line.replace('\n', '')
            if len(line) == 0:
                continue

            if recording:
                if line.lstrip().startswith(stateConfig['sentinel']):
                    break
                tokens = line.split()
                tokens = [token.replace('*','') for token in tokens]

                digInds = list(filter(lambda i: tokens[i].isdigit(), range(len(tokens))))
                lastInd = 0
                for digInd in digInds:
                    county = ' '.join(tokens[lastInd : digInd])
                    cases = tokens[digInd]
                    lastInd = digInd + 1
                    df = df.append({
                        'County': county,
                        'State': state,
                        'Cases': cases,
                        'Deaths': 0,  # update to non-zero
                        'Recovered': 0}, ignore_index=True)  # update to non-zero

            elif headerMatcher.match(line):
                recording = True
                print('found')
    print(lines)

    df['Deaths'] = 0
    df['Recovered'] = 0
    df['State'] = state

    return df


def scrapeImage(stateConfig, state, pagecontent):
    df = pd.DataFrame()
    # Save the image
    imgSuffix = stateConfig['url'][stateConfig['url'].rindex('.'):]
    with open('_tmp/tmp' + imgSuffix, 'wb') as imgFile:
        imgFile.write(pagecontent)


    with Image.open('_tmp/tmp' + imgSuffix) as img:
        img = img.crop((stateConfig['imgLeftPx'], stateConfig['imgUpperPx'], stateConfig['imgRightPx'], stateConfig['imgLowerPx']))
        #img.show()
        img.save('_tmp/tmp2' + imgSuffix)

        # Use psm mode 6: 'Assume a single uniform block of text.'
        customTesseractConfig = r'--psm 6'
        data = pytesseract.image_to_string(img, config=customTesseractConfig)

        lines = data.split('\n')
        prevCount = 2 ** 31 # big number
        allTokens = [line.split() for line in lines]

        print(allTokens)
        ind = 0
        while ind < len(allTokens):
            tokens = allTokens[ind]

            tokens[-1] = ''.join([ch for ch in tokens[-1] if ch.isdigit()])
            print('toks', tokens)


            # Do we need to fix up missing '1' at beginning of previous county?
            numCases = int(tokens[-1])
            if numCases > prevCount:
                # Remove and try again
                print('num cases', numCases, 'greater than prev', prevCount, 'going back to redo', ' '.join(allTokens[ind-1][0:-1]))
                df.drop(df.tail(1).index, inplace=True)
                allTokens[ind-1][-1] = '1' + allTokens[ind-1][-1]
                ind -= 1
                prevCount = int(df.at[len(df)-1, 'Cases'])
                print(prevCount)
                continue

            prevCount = numCases
            df = df.append({
                'County': ' '.join(tokens[0 : -1]),
                'State': state,
                'Cases': numCases,
                'Deaths': 0,  # update to non-zero
                'Recovered': 0}, ignore_index=True)  # update to non-zero
            ind += 1

    return df

scrapeFuncs = {
    'img': scrapeImage,
    'api-json': scrapeApiJson,
    'pdf': scrapePdf,
    'table': scrapeHtmlTable,
    'csv': scrapeCsv,
    'text': scrapeText
}

with open('stateConfig.yml') as configFile:
    pd.set_option('display.max_rows', None)
    configs = yaml.safe_load(configFile)

    # if specified on command line, do only those states. otherwise do all
    states = list(configs['states'].keys())
    args = sys.argv

    if len(sys.argv) > 1:
        if sys.argv[1] == '-a':

            states = states[states.index(sys.argv[2]) : ]
        else:
            states = sys.argv[1:]

    # Process each state
    aggrDf = pd.DataFrame()
    for state in states:
        print('DOING STATE', state)
        stateConfig = configs['states'][state]

        type = getOrDefault(stateConfig, 'type', 'table')
        if type not in scrapeFuncs:
            print('Unsupported type', type)
            continue

        if getOrDefault(stateConfig, 'dateInUrl', False):
            stateConfig['url'] = mangleDateInUrl(stateConfig)

        if 'doJsRender' in stateConfig and stateConfig['doJsRender']:
            sleepAfterRender = getOrDefault(stateConfig, 'sleepAfterRender', 5)
            pagecontent = doJsRender(stateConfig['url'], sleepAfterRender)
        else:
            pagecontent = getSiteContent(stateConfig['url'])

        statedf = scrapeFuncs[type](stateConfig, state, pagecontent)
        statedf = statedf.astype({'Deaths': 'int64', 'Cases': 'int64', 'Recovered': 'int64'})
        statedf = statedf[['County', 'State', 'Cases', 'Deaths', 'Recovered']]

        print(statedf)
        print(statedf.dtypes)
        aggrDf = aggrDf.append(statedf)
    print(aggrDf)
    aggrDf.to_csv('data/out.csv', index=False)
    print("Saved to data/out.csv")
