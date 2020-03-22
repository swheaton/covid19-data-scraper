import pandas as pd
import yaml
import datetime as dt

with open('stateConfig.yml') as configFile:
    configs = yaml.safe_load(configFile)
    print(configs)

    aggrDf = pd.DataFrame()
    for state in configs['states']:
        print('DOING STATE', state)
        stateConfig = configs['states'][state]
        skiprows = 0
        if 'skiprows' in stateConfig:
            skiprows = stateConfig['skiprows']

        df = pd.read_html(stateConfig['url'], skiprows=skiprows, header=0)[0]

        columnRename = {stateConfig['countyRow']: 'County', stateConfig['casesColumn']: 'Cases'}
        df.rename(columns=columnRename, inplace=True)

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

        # Drop last (total col) if needed
        if stateConfig['totalColumn']:
            df = df[:-1]

        print (df.describe())
        print(df.dtypes)
        print(df)