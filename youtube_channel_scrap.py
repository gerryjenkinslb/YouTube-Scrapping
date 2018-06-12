from bs4 import BeautifulSoup
import re
import requests
import csv
import time
import json

# version 1.1 added handling of youtube.com/channel/
#  to already handling of youtube.com/user based channels

# NOTE: url gets to youtube are throttled to 3 seconds between requests
# this is an ad hoc attempt to look like a human to youtube
# so youtube does not start limiting access
wait_between_requests = 3

""" scrape youtube channel to build table of contents html file and 
    csv of video information for excel file
    note this code has a slow down delay to meet youtube terms of use
"""

# set youtube channel name here
channel_name = 'gjenkinslbcc'


youtube_base = 'https://www.youtube.com/'
# others to try
#  gotreehouse  howgrowvideo  gjenkinslbcc howgrowvideo
# by channel name:
#  UCu8YylsPiu9XfaQC74Hr_Gw  UCn34N9fj3x92kOGnQQdHkAQ
# UCH4aPBlmmW1Vgs0ykktCMUg

parent_folder = ''  # users or channel or empty


def get_soup(url):
    """open url and return BeautifulSoup object, 
       or None if site does not exist"""
    
    result = requests.get(url)
    if result.status_code != 200: return None
    time.sleep(wait_between_requests)  # slow down to human speed
    return BeautifulSoup(result.text, 'html.parser')


def channel_section_links(channel_name):
    """list of 
       { 'title': <section title>, 
         'link': <url to section play lists> 
       }"""

    global parent_folder

    soup = get_soup(f'{youtube_base}/user/{channel_name}/playlists')
    if soup is None or 'This channel does not exist.' in soup.text:
        url = f'{youtube_base}/channel/{channel_name}/playlists'
        soup = get_soup(url)
        if soup is None or 'This channel does not exist.' in soup.text:
            raise ValueError(
                'The channel does not exists: ' + channel_name)
        parent_folder = 'channel/'

    play_list_atags = \
        soup.find_all('a',
                      {'href': re.compile(f'{channel_name}/playlists')})
    # filter out non user play lists next
    elements = [{'title': x.text.strip(),
                 'link': fix_url(x['href'])} for x in play_list_atags
                if x.span and
                ('shelf_id=0' not in x['href'])]

    # no sections, make up no sections section with default link
    if len(elements) == 0:
        url = f'{youtube_base}{parent_folder}{channel_name}/playlists'
        elements = [ {'title': 'no sections', 'link': url}]
        # i.e.  https://youtube.com/gotreehouse/playlists
    return elements


def fix_url(url):  # correct relative urls back to absolute urls
    if url[0] == '/':
        return youtube_base + url
    else:
        return url


def get_playlists(section):
    """returns list of list of
    { 'title': <playlist tile>, <link to all playlist videos> }"""
    global parent_folder
    print(f"  getting playlists for section: {section['title']}")

    soup = get_soup(section['link'])
    if soup is None: # no playlist, create dummy with default link
        url = f'{youtube_base}{parent_folder}{channel_name}/videos'
        return [
           {'title': 'No Playlists', 'link':url }]
    atags = soup('a', class_='yt-uix-tile-link')

    playlists = []
    for a in atags:  # find title and link
        title = a.text
        if title != 'Liked videos': # skip these
            url = fix_url(a['href'])
            playlists.append({'title': title, 'link': url})

    if not playlists:  # no playlists
        url = f'{youtube_base}/{parent_folder}{channel_name}/videos'
        return [{'title': 'No Playlists', 'link': url}]

    return playlists

def parse_video(vurl):
    # return dict of
    # title, link, views, publication_date,
    # description, short_link, likes, dislikes

    d = {'link': vurl, 'views': None, 'short_link': vurl,
         'likes': None, 'dislikes': None}

    # now get video page and pull information from it
    vsoup = get_soup(vurl)

    o = vsoup.find('title')
    vtitle = o.text.strip()
    xending = ' - YouTube'
    d['title'] = vtitle[:-len(xending)] \
        if vtitle.endswith(xending) else vtitle
    print(f"      processing video '{d['title']}'" )

    # o is used in the code following to
    # catch missing data targets for scrapping
    o = vsoup.find('div', class_='watch-view-count')
    if o:
        views = o.text
        d['views'] = ''.join(c for c in views if c in '0123456789')

    o = vsoup.find('strong', class_='watch-time-text')
    d['publication_date'] = \
        o.text[len('Published on ') - 1:] if o else ''

    o = vsoup.find('div', id='watch-description-text')
    d['description'] = o.text if o else ''

    o = vsoup.find('meta', itemprop='videoId')
    if o:
        vid = o['content']
        d['short_link'] = f'https://youtu.be/{vid}'

    o = vsoup.find('button',
                   class_='like-button-renderer-like-button')
    if o:
        o = o.find('span', class_='yt-uix-button-content')
        d['likes'] = o.text if o else ''

    o = vsoup.find('button',
                   class_='like-button-renderer-dislike-button')
    if o:
        o = o.find('span', class_='yt-uix-button-content')
        d['dislikes'] = o.text if o else ''

    return d


def add_videos(playlist):
    """find videos in playlist[link]
    and add their info as playlist[videos] as list"""
    surl = playlist['link']
    soup = get_soup(surl)
    print(f"    getting videos for playlist: {playlist['title']}")

    videos = []

    # items are list of video a links from list
    items = soup('a', class_='yt-uix-tile-link')

    # note first part of look get info from playlist page item,
    # and the the last part opens the video and gets more details
    if len(items) > 0:
        for i in items:
            d = dict()
            vurl = fix_url(i['href'])
            t = i.find_next('span', {'aria-label': True})
            d['time'] = t.text if t else 'NA'

            d.update(parse_video(vurl))
            videos.append(d)

    else:  # must be only one video
        d = {'time': 'NA'}
        d.update(parse_video(surl))
        videos.append(d)

    # add new key to this playlist of list of video infos
    playlist['videos'] = videos
    print()


def tag(t,c):
    return f'<{t}>{c}</{t}>' # return html tag with content


def link(text, url): # return a tag with content and link
    return f'<a href="{url}">{text}</a>'


def html_out(channel, sections):
    """create and write channel_name.html file"""
    title = f'YouTube Channel {channel}'
    f = open(f'{channel}.html','w')
    template = ('<!doctype html>\n<html lang="en">\n<head>\n'
                '<meta charset="utf-8">'
                '<title>{}</title>\n</head>\n'
                '<body>\n{}\n</body>\n</html>')

    parts = list()
    parts.append(tag('h1', title))

    for s in sections:
        parts.append(tag('h2',link(s['title'], s['link'])))
        for pl in s['playlists']:
            parts.append(tag('h3', link(pl['title'], pl['link'])))
            if len(pl) == 0:
                parts.append('<p>Empty Playlist</p>')
            else:
                parts.append('<ol>')
                for v in pl['videos']:
                    t = '' if v['time'] == 'NA' else f" ({v['time']})"
                    parts.append(tag('li', link(v['title'],
                                     v['short_link']) + t))
                parts.append('</ol>')
    f.write(template.format(channel, '\n'.join(parts)))
    f.close()


def csv_out(channel, sections):
    """ create and output channel_name.csv
    file for import into a spreadsheet or DB"""
    headers = ('channel,section,playlist,video,'
               'link,time,views,publication date,'
               'likes,dislikes,description').split(',')

    with open(f'{channel}.csv', 'w') as csv_file:
        csvf = csv.writer(csv_file, delimiter=',')
        csvf.writerow(headers)
        for section in sections:
            for playlist in section['playlists']:
                for video in playlist['videos']:
                    v = video
                    line = [channel,
                            section['title'],
                            playlist['title'],
                            v['title']]
                    line.extend([v['short_link'],
                                 v['time'], v['views'],
                                 v['publication_date'],
                                 v['likes'], v['dislikes'],
                                 v['description']])
                    csvf.writerow(line)

def process_channel(channel_name):
    sections = channel_section_links(channel_name)
    for section in sections:
        section['playlists'] = get_playlists(section)
        for playlist in section['playlists']:
            add_videos(playlist)
    return sections


if __name__ == '__main__':
    # find channel name by going to channel
    # and picking last element from channel url
    # for example my channel url is:
    #   https://www.youtube.com/user/gjenkinslbcc
    # my channel name is gjenkinslbcc in this url
    # this is set near top of this file
    # if the channel is of the form:
    # https://www.youtube.com/channel/xyz then supply xyz

    print(f'finding sections for youtube.com {channel_name}')
    sections = process_channel(channel_name)

    # save sections structure to json file
    with open(f'{channel_name}.json','w') as f:
        f.write(json.dumps(sections, sort_keys=True, indent=4))

    html_out(channel_name, sections)  # create web page of channel links

    # create a csv file of video info for import into spreadsheet
    csv_out(channel_name, sections)

    print(f"Program Complete,\n  '{channel_name}.html' and"
          f" '{channel_name}.csv' have been" 
          f" written to current directory")
