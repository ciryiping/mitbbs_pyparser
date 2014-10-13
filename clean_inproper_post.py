# -*- coding: utf-8 -*-

""" Delete posts on MitBBS that contains dirty/inproper words

    The program is only compatible with Python (>=3.2.0)

    The program will:
    1. login to http://www.mitbbs.com/
    2. scan through each post of a page:
       - if the main post (first post) contains dirty/inproper words, delete the entire post
       - if any comment contains dirty/inproper words, delete that comment
       - move to the next post if error occurs
    3. @TODO: log all changes with userid|post content

    Depends:
       - BeautifulSoup4
       - requests
    
    Author: Yue Zhao (yzhao0527@gmail.com)
    Date:   2014-10-12
"""
import re, sys
from bs4 import BeautifulSoup
import requests

# ===== User configuration =====
USERID   = 'Your User Name Here'
PASSWD   = 'Your Password Here'
URL      = "http://www.mitbbs.com/bbsdoc/NewYork.html"
DICTFILE = "wordDict.txt" # each line is treated as one word and converted to lower case.
# ===== End of User configuration =====

# load the dirty word list
with open(DICTFILE, "r") as f:
    wordList = [w.lower() for w in [w.strip() for w in f.readlines()] if len(w) > 0]

# Find dirty words in the given text
# INPUT:
#        text: a string
#    wordList: a list of words to be searched for
# OUTPUT:
#    the first word in the list that appears in the text,
#    return None if no such word exists
# COMMENT:
#    consider using regex (import re) for fancy matching.
def findWord(text, wordList):
    text = text.lower()
    for w in wordList:
        if text.find(w) != -1:
            return w

# Parse Delete Button Arguments
# INPUT:
#    d: the html:<a> entry corresponding to the delete operation
# OUTPUT:
#    a list of 3 arguments used to delete a post
def parseDelOpts(d):
    t = re.search(r'\(.*\)', d['onclick']).group(0)
    t = t[1:-1]
    opts = t.split(',')
    opts[0] = opts[0][1:-1]
    return opts

# Parse Delete Button Arguments
# INPUT:
#    p: the content of a raw bbs post text
# OUTPUT:
#    the original post with title hided
def cleanPost(p):
    inx = p.find(u'发信站')
    return p[inx:]

# Delete a post
# INPUT:
#        d: data used to delete the post
#     opts: form data used to delete the post
#  cookies: cookies with login data
#      ask: interactive mode if true
# OUTPUT:
#      Boolean, whether the deletion operation succeeded
def deletePost(d, opts, cookies, ask=True):
    if ask:
        print("Delete post? [y/n]", end=" ")
        ans = input()
        if len(ans) == 0:
            ans = 'n'
        ans = ans[0].lower()
        if ans != 'y':
            print("Post is NOT delete.")
            return False
    delFormOpts = opts.copy()
    delFormOpts['file']     = d[0]
    delFormOpts['id']       = d[1]
    delFormOpts['dingflag'] = d[2]
    
    r = requests.post(r'http://www.mitbbs.com/mitbbs_bbsdel.php',
                      data=delFormOpts, cookies = cookies, allow_redirects=True)
    r.encoding = "gb2312"
    if r.text.find(r"删除成功") != -1: #@TODO: there must be a better way to do this
        print(r"succeed.")
        return True
    else:
        print(r"failed")
        return False
    
# login to http://www.mitbbs.com
auth = {'id' : USERID, 'passwd' : PASSWD, 'kick_multi' : '1'}
session = requests.session()
session.post("http://www.mitbbs.com/newindex/mitbbs_bbslogin.php", data=auth)


# ========= START PARSING WEBPAGE DATA ==========

# fetch webpage and make 'a beautiful soup'
r   = requests.get(URL, cookies=session.cookies)
r.encoding = "gb2312"

soup = BeautifulSoup(r.text)

# C. parse each article
itemHolder = soup.findAll('td', {'class' : 'taolun_leftright'})
items      = itemHolder[0].findAll('a', {'class' : 'news1'})

for n, item in enumerate(items):
    
    if n % 10 == 9:
        print("Processed {} posts".format(n + 1))
    
    title = item.text.strip()
    link  = r'http://www.mitbbs.com/' + item['href']
    
    try:

        # Read the content of a post
        r     = requests.get(link, cookies=session.cookies)
        r.encoding = "gb2312"
        soup  = BeautifulSoup(r.text)
        
        boxes = [u.parent for u in soup.findAll("td", {"class" : "wenzhang_bg"})]
        users = [b.find('a').text.strip() for b in boxes]
        posts = [b.find('td', {"class" : "jiawenzhang-type"}) for b in boxes]
        delButtons = [b.find("a", text=u"删除") for b in boxes]
        
        # Data quality check
        # @TODO: Error is not handled
        if len(users) != len(posts) or len(users) != len(delButtons):
            raise Exception("size mismatch: " +
                            "(# of users == # of posts == # of delButtons) is violated.")
        
        for u, p, d in zip(users, posts, delButtons):
            if u == None or p == None or d == None:
                raise Exception("content error: None returned for user/post/delButton.")
        
        posts   = [cleanPost(p.text) for p in posts]
        delOpts = [parseDelOpts(d) for d in delButtons]
        
        # Parse delete form
        delForm      = soup.find("form", {'name' : 'delform'})
        delFormItems = delForm.findAll('input')
        delFormOpts  = {t['name'] : t['value'] if t.has_attr('value') else '' for t in delFormItems}
        
        # Scan through each post
        isDirty = False
        info    = [] # I used a list in case the one needs to put in more text
        for i, (u, p, d) in enumerate(zip(users, posts, delOpts)):
            found = findWord(p, wordList)
            if found != None:
                isDirty = True
                if i == 0: # The first article is treated as the main article
                    info.append("The main article contains: " + found)
                    break
                else:      # All other articles are treated as comments
                    info.append("         A reply contains: " + found)
                    break
        if isDirty: # @TODO: add more criteria
            print("   Dirty word Found in post: " + title)
            print("      " + info[0])
            deletePost(d, delFormOpts, cookies=session.cookies, ask=True)

    except Exception as e:
        print("Error occured {} for {}.".format(str(e), title))

print("done")
