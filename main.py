#!/usr/bin/env python
#

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api.urlfetch import fetch
import datetime
import models
import hutils
import re

################################################################################
#                        SymPullCDN Configuration                              #
################################################################################
#                                                                              #
#  1. Origin                                                                   #
#     The origin server will be mirrored by this instance of SymPullCDN        #
#     configure a full http:// path with a FQDN, trailing slash included       #
origin = "http://replace*me/"                                                  #
#                                                                              #
#  2. Cachable Codes                                                           #
#     This is a list of HTTP Status Codes that will be cached when sent from   #
#     the origin.  By default only 200 OK codes will be cached.  Edit this     #
#     list only if you have a reason.                                          #
#                                                                              #
cache_codes = ( 200, )                                                         #
#                                                                              #
#                                                                              #
################################################################################





# Compiled Regular Expressions
no_cache_regex = re.compile( "(no-cache|no-store|private)", re.IGNORECASE )

class Entity(db.Model):
    uri          = db.StringProperty(required=True)
    LastModified = db.StringProperty()
    headers      = models.DictProperty()
    expires      = db.DateTimeProperty()
    status       = db.IntegerProperty()
    content      = db.BlobProperty(required=True)

class MainHandler(webapp.RequestHandler):
    def get(self):

       ############################################################################################
       #                                                                                          #
       #        Getting entity from cache, Passing to the user, possibly revalidating it          #  
       #                                                                                          #
       ############################################################################################
       
        entity = Entity.all().filter("uri =", self.request.path).get()
        if entity:
            # Revalidate if required.  Note, revalidation here updates the
            # request /after/ this one for the given entity.
            if entity.expires <= datetime.datetime.now():
                request_entity = fetch( origin + self.request.path, method="GET", 
                        headers={"If-Modified-Since" : entity.LastModified} )
                
                # If 304 JUST update the headers.
                if request_entity.status_code == 304:
                    headers      = dict(request_entity.headers)
                    entity.expires = hutils.get_expires( request_entity.headers )
                    entity.LastModified = hutils.get_header( "Last-Modified", request_entity.headers )
                    entity.save()
                # If 200, update the content too.
                elif request_entity.status_code == 200:
                    headers      = dict(request_entity.headers)
                    entity.expires = hutils.get_expires( request_entity.headers )
                    entity.LastModified = hutils.get_header( "Last-Modified", request_entity.headers )
                    entity.content = request_entity.content
                    entity.save()
                #Revalidation failed, send the entity stale and delete from the cache.
                else:
                    for key in iter(entity.headers):
                        self.response.headers[key] = entity.headers[key]
                    self.response.set_status(entity.status)
                    self.response.headers["X-SymPullCDN-Status"] = "Hit[EVALIDFAIL]"
                    self.response.out.write(entity.content)
                    entity.delete()
                    return True
            
            # See if we can send a 304
            if "If-Modified-Since" in self.request.headers:
                if self.request.headers["If-Modified-Since"] == entity.LastModified:
                    for key in iter(entity.headers):
                        self.response.headers[key] = entity.headers[key]
                    self.response.set_status(304)
                    self.response.headers["X-SymPullCDN-Status"] = "Hit[304]"
                    self.response.out.write(None)
                    return True

            for key in iter(entity.headers):
                self.response.headers[key] = entity.headers[key]
            self.response.set_status(entity.status)
            self.response.headers["X-SymPullCDN-Status"] = "Hit[200]"
            self.response.out.write(entity.content)
            return True
       
       ############################################################################################
       #                                                                                          #
       #             Fetching The Entity, Passing it to the user, possibly storing it             #  
       #                                                                                          #
       ############################################################################################
       
        request_entity = fetch( origin + self.request.path, method="GET", payload=None )
        
        # Respect no-cache and private
        if "Cache-Control" in request_entity.headers:
            m = no_cache_regex.match( request_entity.headers["Cache-Control"] )
            if m:
                self.response.headers["X-SymPullCDN-Status"] = "Miss[NoCtrl]"
                for key in iter(request_entity.headers):
                    self.response.headers[key] = request_entity.headers[key]
                self.response.out.write(request_entity.content)
                return True
        # Only Cache Specific Codes
        if request_entity.status_code not in cache_codes:
            self.response.headers["X-SymPullCDN-Status"] = "Miss[NoCode]"
            for key in iter(request_entity.headers):
                self.response.headers[key] = request_entity.headers[key]
            self.response.set_status(request_entity.status_code)
            self.response.out.write(request_entity.content)
            return True
        
        # Set up data to store.
        entity = Entity(
            uri          = self.request.path,
            headers      = dict(request_entity.headers),
            expires      = hutils.get_expires( request_entity.headers ),
            LastModified = hutils.get_header( "Last-Modified", request_entity.headers ),
            status       = request_entity.status_code,
            content      = request_entity.content).save()

        for key in iter(request_entity.headers):
            self.response.headers[key] = request_entity.headers[key]
        self.response.headers["X-SymPullCDN-Status"] = "Miss[Cached]"
        self.response.out.write(request_entity.content)


def main():
    application = webapp.WSGIApplication([('/.*', MainHandler)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
