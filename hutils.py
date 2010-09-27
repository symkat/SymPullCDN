#!/usr/bin/env python

import datetime
import re

# Compiled regexs
find_n_max_age = re.compile( r"max-age=(\d+)", re.IGNORECASE )
find_s_max_age = re.compile( r"s-maxage=(\d+)", re.IGNORECASE ) 

# Given the headers from a request object find the time when the 
# entity must be refreshed in the cache.
# Order of presidence: 
# 1. Cache-Control: s-maxage 
# 2. Cache-Control: max-age 
# 3. Now + ( Expires - Date ) 
# 4. Set a default cache delta

def get_expires( headers ):
    if "Cache-Control" in headers:
        s_maxage = find_s_max_age.match( headers["Cache-Control"] )
        max_age = find_n_max_age.match( headers["Cache-Control"] )
        if s_maxage:
            return datetime.datetime.now() + datetime.timedelta(int(s_maxage.group(1)))
        elif max_age:
            return datetime.datetime.now() + datetime.timedelta(seconds=int(max_age.group(1)))
    
    if "Expires" in headers:
        h_expires = datetime.datetime.strptime( headers["Expires"], "%a, %d %b %Y %H:%M:%S GMT"  )
        h_date    = datetime.datetime.strptime( headers["Date"], "%a, %d %b %Y %H:%M:%S GMT"  )
        delta     = datetime.timedelta = h_expires - h_date
        return datetime.datetime.now() + delta
    
    return datetime.datetime.now() + datetime.timedelta( days=7 )

def get_header( want, headers ):
    if want in headers:
        return headers[want]
    else:
        return None
