import pandas as pd
import yaml
import numpy as np

def getOrDefault(config: object, attr: object, default: object) -> object:
    retValue = default
    if attr in config:
        retValue = config[attr]
    return retValue

with open('stateConfig.yml') as configFile:
    configs = yaml.safe_load(configFile)

    aggrDf = pd.DataFrame()
    for state in configs['states']:
        print('DOING STATE', state)
        stateConfig = configs['states'][state]
        headerRowsToSkip = getOrDefault(stateConfig, 'headerRowsToSkip', 0)

        tableIndex = getOrDefault(stateConfig, 'tableIndex', 0)

        df = pd.read_html(stateConfig['url'], skiprows=headerRowsToSkip, header=0)[tableIndex]

        # Drop last (total col) if needed
        footerRowsToSkip = getOrDefault(stateConfig, 'footerRowsToSkip', 0)
        if footerRowsToSkip != 0:
            df = df[:-footerRowsToSkip]

        print(df)

        countyCol = getOrDefault(stateConfig, 'countyCol', 'County')
        casesCol = getOrDefault(stateConfig, 'casesCol', 'Cases')
        columnRename = dict(zip((countyCol, casesCol), ('County', 'Cases')))
        df.rename(columns=columnRename, inplace=True)

        print(df)

        # Extract number if cases col is string
        if df['Cases'].dtype == np.object:
            df['Cases'] = df['Cases'].str.extract('(?P<Cases>\d*)')

        # Remove all extraneous columns
        df.drop(df.columns.difference(['County','Cases', 'Deaths', 'Recovered']), axis=1, inplace=True)

        # Add deaths column if not present
        if 'Deaths' not in df:
            df['Deaths'] = 0
        else:
            df['Deaths'].fillna(0, inplace=True)

        # Add recovered column if not present
        if 'Recovered' not in df:
            df['Recovered'] = 0
        else:
            df['Recovered'].fillna(0, inplace=True)

        df = df.astype({'Deaths': 'int64', 'Cases': 'int64', 'Recovered': 'int64'})

        # Add state column
        df['State'] = state

        # Reorder columns
        df = df[['County', 'State', 'Cases', 'Deaths', 'Recovered']]

        print (df.describe())
        print(df.dtypes)
        print(df)