from bs4 import BeautifulSoup
import re, requests, csv, time

""" scrape youtube channel to build table of contents html file and 
    csv of video information for excel file
    note this code has a slow down delay to meet youtube terms of use
"""
# set youtube channel name here
channel_name = "gjenkinslbcc"

def get_soup(url):
    """open url and return BeautifulSoup object, or None if site does not exist"""
    result = requests.get(url)
    if result.status_code != 200: return None
    time.sleep(5) # slow down as per youtube 'terms of use' to human speed
    return BeautifulSoup(result.text, 'html.parser')

def channel_section_links():
    '''list of { 'title': <section title>, 'link': <url to section play lists> }'''
    soup = get_soup(f"https://www.youtube.com/user/{channel_name}/playlists")
    if 'This channel does not exist.' in soup.text:
        raise ValueError("The channel does not exists: " + channel_name)

    play_list_atags = soup.find_all('a', {'href': re.compile(f"{channel_name}/playlists")})
    elements = [{'title': x.text.strip(), "link": fix_url(x['href'])} for x in play_list_atags if
                x.span and ('shelf_id=0' not in x['href'])] # filter out non user play lists

    if len(elements) == 0: # no sections, make up no sections section with default link
        elements = [ {'title':'no sections',
                      'link':f'https://youtube.com/{channel_name}/playlists'}]

    return elements


def fix_url(url):  # correct relative urls back to absolute urls
    if url[0] == '/': return 'https://www.youtube.com' + url
    else: return url


def get_playlists(section):
    """returns list of list of { 'title': <playlist tile>, <link to all playlist videos> }"""
    print(f"  getting playlists for section: {section['title']}")
    soup = get_soup(section['link'])
    if soup == None: # no playlist, create dummy playlist and default link
       return [{'title':'No Playlists', 'link':f'https://youtube.com/{channel_name}/videos'}]
    atags = soup('a', class_="yt-uix-tile-link")

    playlists = []
    for a in atags:  # find title and link
        title = a.text
        if title != "Liked videos": # skip these
            link = fix_url(a['href'])
            playlists.append({'title':title, 'link':link})
    if playlists == []: return [{'title':'No Playlists',
                                 'link':f'https://youtube.com/{channel_name}/videos'}]
    return playlists

def add_videos(playlist):
    """find videos in playlist[link] and add their info as playlist[videos] as list"""
    soup = get_soup(playlist['link'])
    print(f"    getting videos for playlist: {playlist['title']}")
    items = soup('a', class_="yt-uix-tile-link") # items are list of video a links from list
    videos = []
    for i in items: # note first part of look get info from playlist page item, and the the last part opens
                    # the video and gets more details
        d = {} # collect video info in dict
        d['title'] = i.text.strip()
        link = fix_url(i['href'])
        d['link'] = link
        t = i.find_next('span', { 'aria-label': True})
        d['time'] = t.text if t else 'NA'
        print(f"      open video '{d['title']}' for details", end=" ")

        vsoup = get_soup(link) # now get video page and pull information from it
        print("* read, now processing",end="")
        views= vsoup.find('div', class_='watch-view-count').text
        d['views'] = ''.join(c for c in views if c in "0123456789")
        d['publication_date'] = vsoup.find('strong',
                                class_="watch-time-text").text[len('Published on ')-1:]
        d['description'] = vsoup.find('div',id='watch-description-text').text
        id = vsoup.find('meta', itemprop="videoId")['content']
        d['short_link'] = f'https://youtu.be/{id}'
        likebutton = vsoup.find('button', class_="like-button-renderer-like-button")
        d['likes'] = likebutton.find('span',class_ = 'yt-uix-button-content').text
        disbutton = vsoup.find('button',class_='like-button-renderer-dislike-button')
        d['dislikes'] = disbutton.find('span',class_ = 'yt-uix-button-content').text
        videos.append(d)
        print("* finished video")

        playlist['videos'] = videos # add new key to this playlist of list of video infos

def tag(t,c): return f'<{t}>{c}</{t}>' # return html tag with content
def link(text, url): return f'<a href="{url}">{text}</a>' # return a tag with content and link

def html_out(channel, sections):
    '''create and write channel_name.html file'''
    title = f"YouTube Channel {channel}"
    f = open(f"{channel}.html",'w')
    template = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">' + \
    '<title>{}</title>\n</head>\n<body>\n{}\n</body>\n</html>'

    parts = []
    parts.append(tag('h1', title))

    for section in sections:
        parts.append(tag('h2',link(section['title'], section['link'])))
        for playlist in section['playlists']:
            parts.append(tag('h3',link(playlist['title'], playlist['link'])))
            parts.append('<ol>')
            for video in playlist['videos']:
                parts.append(tag('li',link(video['title'], video['short_link']) \
                                 + ' (' + video['time'] + ")"))
            parts.append('</ol>')
    f.write(template.format(channel, '\n'.join(parts)))
    f.close()

def csv_out(channel, sections):
    """ create and output channel_name.csv file for import into a spreadsheet or DB"""
    headers = 'channel,section,playlist,video,' + \
              'link,time,views,publication date,likes,dislikes,description'.split(',')

    with open(f'{channel}.csv', "w") as csv_file:
        csvf = csv.writer(csv_file, delimiter=',')
        csvf.writerow(headers)
        for section in sections:
            for playlist in section['playlists']:
                for video in playlist['videos']:
                    v = video
                    line = [ channel, section['title'], playlist['title'], v['title']]
                    line.extend([v['short_link'],v['time'], v['views'], v['publication_date'],
                                 v['likes'], v['dislikes'], v['description']])
                    csvf.writerow(line)

if __name__ == '__main__':
    # find channel name by going to channel and picking last element from channel url
    # for example my channel url is: https://www.youtube.com/user/gjenkinslbcc
    # my channel name is gjenkinslbcc in this url
    # this is set near top of this file

    print("finding sections")
    sections = channel_section_links()
    for section in sections:
        section['playlists'] = get_playlists(section)
        for playlist in section['playlists']:
            add_videos(playlist)

    html_out(channel_name, sections) # create web page of channel links
    csv_out(channel_name, sections) # create a csv file of video info for import into spreadsheet

    print(f"Program Complete,\n  '{channel_name}.htm' and" \
          f" '{channel_name}.csv' have been written to current directory")
