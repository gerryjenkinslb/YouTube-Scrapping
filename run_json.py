
import json
from youtube_channel_scrap import *

if __name__ == '__main__':
    # output from json dump of last run

    print(f'getting sections from {channel_name}.json')
    with open(f"{channel_name}.json", 'r') as f:
        sections = json.loads(f.read())

    # save sections structure to json file
    with open(f'{channel_name}.json','w') as f:
        f.write(json.dumps(sections, sort_keys=True, indent=4))

    html_out(channel_name, sections)  # create web page of channel links

    # create a csv file of video info for import into spreadsheet
    csv_out(channel_name, sections)

    print(f"Program Complete,\n  '{channel_name}.htm' and"
          f" '{channel_name}.csv' have been" 
          f"written to current directory")