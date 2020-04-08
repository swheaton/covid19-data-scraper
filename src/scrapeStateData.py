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


def getSiteContent(url, rawContent):
    # Doing this to look more like a browser so we won't get denied.
    header = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    r = None
    content = None
    try:
        r = requests.get(url, headers=header)
        if rawContent:
            content = r.content
        else:
            content = r.text
    except requests.exceptions.SSLError:
        print('SSLError, trying to fake SSL context')
        context = ssl._create_unverified_context()
        r = urllib.request.urlopen(url, context=context)
        content = r.read()
    return content


def mangleDateInUrl(dateInUrlConfig, url):
    yesterday = getOrDefault(dateInUrlConfig, 'yesterday', False)
    date = datetime.today()
    if yesterday:
        date = date - timedelta(days=1)
    zeroPad = getOrDefault(dateInUrlConfig, 'zeroPad', 'none')
    outDate = ''
    if zeroPad == 'none':
        outDate = date.strftime(dateInUrlConfig['dateFormat'])
    elif zeroPad == 'first':
        tokens = dateInUrlConfig['dateFormat'].split('%')
        outDate = tokens[0] + date.strftime('%'+tokens[1]).lstrip('0') + date.strftime('%' + '%'.join(tokens[2:]))
    elif zeroPad == 'all':
        tokens = dateInUrlConfig['dateFormat'].split('%')
        outDate = tokens[0]
        tokens = tokens[1:]
        for token in tokens:
            outDate = outDate + date.strftime('%'+token).lstrip('0')

    if getOrDefault(dateInUrlConfig, 'toLower', False):
        outDate = outDate.lower()
    mangledUrl = url.replace('{{INSERT_DATE}}', outDate)
    print(mangledUrl)
    return mangledUrl


def doJsRender(url, tosleep):
    content = None
    with HTMLSession() as session:
        r = session.get(url)
        r.html.render(retries=5, timeout=0, sleep=tosleep)
        content = r.html.html
    return content


def doEstablishAndExtractSession(extractSessionConfig, url):
    sessionEstablishUrl = extractSessionConfig['sessionEstablishUrl']
    with requests.Session() as session:
        response = session.get(sessionEstablishUrl)
        sessionId = response.headers[extractSessionConfig['sessionIdHeader']]
        url = url.replace('{{SESSION_ID}}', sessionId)
        print(extractSessionConfig['formData'])
        print(url)
        response2 = session.post(url, data=extractSessionConfig['formData'])
        return response2.text


def scrapeHtmlTable(scrapeParams, state, pagecontent):
    html = pagecontent

    tableIndex = getOrDefault(scrapeParams, 'tableIndex', 0)
    headerRowsToSkip = getOrDefault(scrapeParams, 'headerRowsToSkip', 0)
    df = pd.read_html(html, skiprows=headerRowsToSkip, header=0)[tableIndex]

    # Drop last (total col) if needed
    footerRowsToSkip = getOrDefault(scrapeParams, 'footerRowsToSkip', 0)
    if footerRowsToSkip != 0:
        df = df[:-footerRowsToSkip]

    assert isinstance(df.columns.str, object)
    # Some random unhelpful unicode characters
    df.columns = df.columns.str.replace('\u200b', '')
    df.columns = df.columns.str.replace('\u0080', '')

    countyCol = getOrDefault(scrapeParams, 'countyCol', 'County')
    casesCol = getOrDefault(scrapeParams, 'casesCol', 'Cases')
    deathsCol = getOrDefault(scrapeParams, 'deathsCol', 'Deaths')
    recoveredCol = getOrDefault(scrapeParams, 'recoveredCol', 'Recovered')
    columnRename = dict(zip((countyCol, casesCol, deathsCol, recoveredCol), ('County', 'Cases', 'Deaths', 'Recovered')))
    df.rename(columns=columnRename, inplace=True)

    df = df[df['County'].notnull()]
    print(df)

    # Extract number if cases col is string.
    #   And also zero-width space first...
    if df['Cases'].dtype == np.object:
        df['Cases'] = df['Cases'].str.replace('\u200b', '')
        df['Cases'] = df['Cases'].str.replace('<5', getOrDefault(scrapeParams, 'replaceLess5', '1'))
        df['Cases'] = df['Cases'].str.extract('(?P<Cases>\d*)')
    else:
        df['Cases'].fillna(0, inplace=True)

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


def scrapeApiJson(scrapeParams, state, pagecontent):
    df = pd.DataFrame()

    if 'objSep' in scrapeParams:
        pagecontentlist = re.split(scrapeParams['objSep'], str(pagecontent))
        pagecontentlist = [pc for pc in pagecontentlist if pc != '']
        pagecontent = '[' + ','.join(pagecontentlist) + ']'

    with open('blah.out', 'w') as b:
        b.write(str(pagecontent))

    jsonResult = json.loads(str(pagecontent))

    if 'listIndexLookup' in scrapeParams:
        indexLookupParams = scrapeParams['listIndexLookup']
        strvalues = dpath.util.get(jsonResult, indexLookupParams['countyValuesDpath'])
        print(strvalues)
        countyIndices = dpath.util.get(jsonResult, indexLookupParams['countyIndicesDpath'])
        print(countyIndices)

        intvalues = dpath.util.get(jsonResult, indexLookupParams['casesValuesDpath'])
        print('values', intvalues)
        indices = dpath.util.get(jsonResult, indexLookupParams['casesIndicesDpath'])
        print('indices', indices)

        assert(len(indices) == len(countyIndices))

        for countyInd in range(len(countyIndices)):
            if 'skipIndices' in indexLookupParams and countyInd in indexLookupParams['skipIndices']:
                continue
            indexOfValue = indices[countyInd]

            if indexOfValue >= 0:
                numCases = intvalues[indexOfValue]
            else:
                numCases = 0
            county = strvalues[countyIndices[countyInd]]
            df = df.append( {
                    'County' : county ,
                    'State' : state,
                    'Cases': numCases or 0,
                    'Deaths': 0,
                    'Recovered': 0} , ignore_index=True)
    else:
        counties = dpath.util.get(jsonResult, scrapeParams['countyListDpath'])
        for countyJson in counties:
            county = dpath.util.get(countyJson, scrapeParams['countyDpath'])

            if getOrDefault(scrapeParams, 'ignoreStateAsCounty', False) and county == state:
                continue
            numCases = dpath.util.get(countyJson, scrapeParams['casesDpath'])
            numDeaths = dpath.util.get(countyJson, scrapeParams['deathsDpath']) if 'deathsDpath' in scrapeParams else 0
            numRecovered = dpath.util.get(countyJson, scrapeParams['recoveredDpath']) if 'recoveredDpath' in scrapeParams else 0
            df = df.append( {
                    'County' : county ,
                    'State' : state,
                    'Cases': numCases or 0,
                    'Deaths': numDeaths or 0,
                    'Recovered': numRecovered or 0} , ignore_index=True)

    return df


def scrapeText(scrapeParams, state, pagecontent):
    tree = htmlparse.fromstring(pagecontent)
    subtree = tree.xpath(scrapeParams['dataXpath'])
    dataString = str(htmlparse.tostring(subtree[0]))

    startIndex = 0
    if 'startDelim' in scrapeParams:
        startDelim = scrapeParams['startDelim']
        startIndex = dataString.find(startDelim) + len(startDelim)
    elif 'firstCounty' in scrapeParams:
        startIndex = dataString.find(scrapeParams['firstCounty'])
    else:
        print("ERROR: did you mean to not have a start delim or first county?")
    sentinel = scrapeParams['sentinel']

    dataString = dataString[startIndex : dataString.find(sentinel)]
    dataList = dataString.split(getOrDefault(scrapeParams, 'eltDelim', ','))

    df = pd.DataFrame()
    for countyDatum in dataList:
        countyDatum = countyDatum.strip().replace('(', '').replace(')', '').replace(':', '')
        countyDatum = re.sub(r'<[^>]+>', '', countyDatum)

        dataTuple = countyDatum.split()
        newInParen = getOrDefault(scrapeParams, 'newInParen', False)
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


def scrapeCsv(scrapeParams, state, pagecontent):
    footerRowsToSkip = getOrDefault(scrapeParams, 'footerRowsToSkip', 0)
    df = pd.read_csv(StringIO(pagecontent), skipfooter=footerRowsToSkip)
    countyCol = getOrDefault(scrapeParams, 'countyCol', 'County')
    casesCol = getOrDefault(scrapeParams, 'casesCol', 'Cases')
    columnRename = dict(zip((countyCol, casesCol), ('County', 'Cases')))
    df.rename(columns=columnRename, inplace=True)
    df['Cases'].fillna(0, inplace=True)
    df['Deaths'] = 0
    df['Recovered'] = 0
    df['State'] = state

    print(df)
    return df


def scrapePdf(scrapeParams, state, pagecontent):
    with open('_tmp/tmp.pdf', 'wb') as pdfFile:
        pdfFile.write(pagecontent)
    try:
        os.remove('_tmp/tmp.txt')
    except FileNotFoundError:
        pass

    pageOfTable = ''
    if 'pageOfTable' in scrapeParams:
        pageOfTable = '-f ' + str(scrapeParams['pageOfTable']) + ' -l ' + str(scrapeParams['pageOfTable'])
    os.system('pdftotext ' + pageOfTable +' -layout _tmp/tmp.pdf')
    df = pd.DataFrame()

    with open('_tmp/tmp.txt', 'r', encoding = "ISO-8859-1") as txtFile:
        lines = txtFile.readlines()
        recording = False
        countyCol = getOrDefault(scrapeParams, 'countyCol', 'County')
        casesCol = getOrDefault(scrapeParams, 'casesCol', 'Cases')

        headerMatcher = re.compile('\s*'+countyCol+'\s*'+casesCol)
        for line in lines:
            line = line.replace('\n', '')
            if len(line) == 0:
                continue

            if recording:
                if line.lstrip().startswith(scrapeParams['sentinel']):
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


def scrapeImage(scrapeParams, state, pagecontent):
    df = pd.DataFrame()
    # Save the image
    imgSuffix = scrapeParams['url'][scrapeParams['url'].rindex('.'):]
    with open('_tmp/tmp' + imgSuffix, 'wb') as imgFile:
        imgFile.write(pagecontent)


    with Image.open('_tmp/tmp' + imgSuffix) as img:
        img = img.crop((scrapeParams['imgLeftPx'], scrapeParams['imgUpperPx'], scrapeParams['imgRightPx'], scrapeParams['imgLowerPx']))
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

needsRawContent = ['img', 'pdf']

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

        scrapeType = getOrDefault(stateConfig, 'type', 'table')
        if scrapeType not in scrapeFuncs:
            print('Unsupported type', scrapeType)
            continue

        if 'dateInUrl' in stateConfig:
            stateConfig['url'] = mangleDateInUrl(stateConfig['dateInUrl'], stateConfig['url'])

        if 'doJsRender' in stateConfig:
            sleepAfterRender = getOrDefault(stateConfig['doJsRender'], 'sleepAfterRender', 5)
            pagecontent = doJsRender(stateConfig['url'], sleepAfterRender)
        elif 'doEstablishAndExtractSession' in stateConfig:
            pagecontent = doEstablishAndExtractSession(stateConfig['doEstablishAndExtractSession'], stateConfig['url'])
        else:
            pagecontent = getSiteContent(stateConfig['url'], stateConfig['type'] in needsRawContent)

        statedf = scrapeFuncs[scrapeType](stateConfig['scrapeParams'], state, pagecontent)
        statedf = statedf.astype({'Deaths': 'int64', 'Cases': 'int64', 'Recovered': 'int64'})
        statedf = statedf[['County', 'State', 'Cases', 'Deaths', 'Recovered']]

        print(statedf)
        print(statedf.dtypes)
        aggrDf = aggrDf.append(statedf)
    print(aggrDf)
    aggrDf.to_csv('data/out.csv', index=False)
    print("Saved to data/out.csv")
