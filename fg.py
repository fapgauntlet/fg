#!/usr/bin/env python

import wx
import wx.animate
import os, os.path
import time
import urllib2
import re
import threading
import sys
from math import sin, cos, radians
from random import randint

# change below to gime.gmtime to bring threads with no bump time to the front (rather than to the back)
BUMPTIME_EMPTY_VAL = time.gmtime(0)

#proxy = {'http':'127.0.0.1:8118'}
proxy = {}


board_names = [
    'a', 'b', 'c', 'd', 'e', 'f', 'gif', 'h', 'hr', 'k', 'm', 'o', 'p', 'r', 
    's', 't', 'u', 'v', 'vg', 'w', 'wg', 'i', 'ic','r9k','cm', 'y', '3', 'adv',
    'an', 'cgl', 'ck', 'co', 'diy', 'fa', 'fit', 'hc', 'hm', 'int', 'jp', 
    'lit', 'mlp', 'mu', 'n', 'po', 'pol', 'sci', 'soc', 'sp', 'tg', 'toy', 
    'trv', 'tv', 'vp', 'x'
]


spam_filters = []
if os.path.exists('spamfilter.cfg'):
    try:
        f = None
        f = open('spamfilter.cfg', 'r')
        f_read = f.read()
        for line in f_read.splitlines():
            spam_filters.append(line)
    except:
        raise
        pass
    finally:
        if f is not None:
            f.close()


def we_are_frozen():
    """Returns whether we are frozen via py2exe.
    This will affect how we find out where we are located."""

    return hasattr(sys, "frozen")


def module_path():
    """ This will get us the program's directory,
    even if we are frozen using py2exe"""

    if we_are_frozen():
        return os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding( )))

    return os.path.dirname(unicode(__file__, sys.getfilesystemencoding( )))


intensities = [
    'extremely light',
    'very light',
    'light',
    'loose',
    'medium',
    'tight',
    'hard',
    'very hard',
    'extremely hard'
]



my_path = module_path()
print my_path

cache_dir = os.path.join(my_path, 'cache/')
thumb_cache = os.path.join(cache_dir, 'thumbs/')

if not os.path.exists(cache_dir) or not os.path.isdir(cache_dir):
    os.mkdir(cache_dir)


g = []

def html_to_text(html):
    html = '"'.join(html.split('&quot;'))
    html = '>'.join(html.split('&gt;'))
    html = '<'.join(html.split('&lt;'))
    html = '&'.join(html.split('&amp;'))
    html = ','.join(html.split('&#44;'))
    html = '\n'.join(html.split('<br />'))
    html = '\n'.join(html.split('<br/>'))
    html = '\n'.join(html.split('<br >'))
    html = '\n'.join(html.split('<br>'))
    return html


def openurl(url, timestamp=None):
    # fix for urllib2 proxy bug
    proxy_support = urllib2.ProxyHandler(proxy)
    opener = urllib2.build_opener(proxy_support)
    
    # create the http request, possibly with a timestamp
    request = urllib2.Request(url)
    if timestamp is not None:
        request.add_header('If-Modified-Since', timestamp)
    
    try:
        url_handle = opener.open(request)
        # got new data
        return url_handle.read(), url_handle.info().getheader("Last-Modified")
    except urllib2.HTTPError, errorInfo:
        if errorInfo.code == 404:
            return 404, None
        if errorInfo.code == 304:
            # no new data
            return None, timestamp
        # some other error
        return errorInfo.code, None


class OpenUrlThreaded(threading.Thread):
    def __init__(self, url, timestamp=None):
        threading.Thread.__init__(self)
        self.url = url
        self.timestamp = timestamp
        self.result = None
    
    def run(self):
        self.result = openurl(self.url, self.timestamp)



def random_page_thread(page_text):
    # yeah this might look weird but regexes are weird
    matches = [x for x in re.finditer(r'\[<a href="([^"]+)">Reply</a>\]', page_text)]
    return matches[randint(0,len(g))%len(matches)].group(1)

def get_thread_image_urls(thread_text):
    r = r'x(\d+)[^)]*?\)</span><br><a href="(http://images.4chan.org[^"]*)" target=_blank><img src='
    matches = [x for x in re.finditer(r, thread_text)]
    return [m.groups() for m in matches]


class ThreadedResult(threading.Thread):
    def __init__(self, call, *a, **k):
        threading.Thread.__init__(self)
        self.call = call
        self.a = a
        self.k = k
        self.result = None
    
    def run(self):
        self.result = self.call(*self.a, **self.k)


class ChanBoard(object):
    def __init__(self, which):
        self.url = 'http://boards.4chan.org/'+which
        self.pages = None
        #self.page_time = [None]*self.pages
        self.page_time = []
        self.threads = {}
    
    def update_iter(self):
        start = 0
        if self.pages is None:
            changed_t, same_t = self.update_page(0)
            yield changed_t, same_t
            start = 1
        for i in xrange(start, self.pages):
            yield self.update_page(i)
    
    def update(self):
        for changed_t, same_t in self.update_iter():
            if ((changed_t and not same_t) or not changed_t) and None not in self.page_time:
                break # everything is current
    
    def update_page(self, i):
        # thread separator
        thread_sep_regex = re.compile(r'<hr(?:[ /][^>]*?)?>')
        # poster name, trip, time, id
        post_header_regex = re.compile(r'>([^<]*)(?:</a>)?</span>(?: <span class="postertrip">([^<]*)</span>)?([^<]*)<span id="no[^"]*"><a href="[^"]*" class="quotejs">No.</a><a href="[^"]*" class="quotejs">([^<]*)</a>')
        i = int(i)
        while len(self.page_time) <= i:
            self.page_time.append(None)
        if i:
            u = self.url+'/'+str(i)
        else:
            u = self.url
        
        html, self.page_time[i] = openurl(u, self.page_time[i])
        if html is None: # page hasn't been modified
            return 0, None
        
        if self.pages is None:
            pagelen_regex = re.compile(r'(?:Previous.*<a href="[\d]*[^"]*">([\d]*)</a>)')
            match = pagelen_regex.search(html)
            try:
                p = int(match.group(1)) + 1
            except AttributeError:
                print html
            self.pages = p
            
            while len(self.page_time) < p:
                self.page_time.append(None)
        
        changed_threads = 0
        same_threads = 0
        thread_area = re.search(r'<form name="delform" action="[^"]*" method=POST>(.*?)</form>', html, re.S).group(1)
        
        threads = thread_sep_regex.split(thread_area)
        
        for t in threads:
            t_url = re.search(r'\[<a href="([^"]+)">Reply</a>\]', t)
            if t_url is None: # junk at the end of the thread area regex
                continue
            t_url = t_url.group(1)
            headers = post_header_regex.finditer(t)
            for h in headers:
                poster_name, poster_trip, t_time, post_id = h.groups()
            #print t_url
            if t_url not in self.threads:
                self.threads[t_url] = ChanThread(self.url+'/'+t_url)
                self.threads[t_url].bump_time = t_time
                self.threads[t_url].need_update = True
                changed_threads += 1
            elif t_time != self.threads[t_url].bump_time:
                #self.threads[t_url].update()
                self.threads[t_url].bump_time = t_time
                changed_threads += 1
            else:
                same_threads += 1
            try:
                added, not_added = self.threads[t_url].update_from_text(t)
                if added == 1 and not_added == 0 and len(self.threads[t_url].posts.items()) == 1: # thread only has op post
                    self.threads[t_url].need_update = False
                if added and not_added == 1: # thread has more replies than are visible
                    self.threads[t_url].need_update = True
            except:
                import traceback
                print 'bad thread:',self.url+'/'+t_url
                traceback.print_exc()
                pass
        
        '''
        for t_match in re.finditer(r'\[<a href="([^"]+)">Reply</a>\]', html):
            t_url = t_match.group(1)
            t_time = 0
            if t_url not in self.threads:
                self.threads[t_url] = ChanThread(self.url+'/'+t_url)
                self.threads[t_url].bump_time = t_time
                changed_threads += 1
            elif t_time != self.threads[t_url].bump_time:
                #self.threads[t_url].update()
                self.threads[t_url].bump_time = t_time
                changed_threads += 1
            else:
                same_threads += 1
        '''
        
        return changed_threads, same_threads
        
    
    def get_thread(self, t_url):
        if t_url not in self.threads or self.threads[t_url] is None:
            self.threads[t_url] = ChanThread(self.url+'/'+t_url)



class ChanThread(object):
    # poster name, trip, time, id
    post_header_regex = re.compile(r'>([^<]*)(?:</a>)?</span>(?: <span class="postertrip">([^<]*)</span>)?([^<]*)<span id="no[^"]*"><a href="[^"]*" class="quotejs">No.</a><a href="[^"]*" class="quotejs">([^<]*)</a>')
    # image name, size, res, url, thumburl
    img_regex = re.compile(r'<span class="filesize">[^<]*<a href="[^"]*" target="_blank">([^<]*)</a>-\(([^,]*), ([^),]*).*?\)</span><br><a href="([^"]*)" target=_blank><img src=(\S*) [^>]*></a>')
    # post subject
    subject_regex = re.compile(r'<span class="[replyfil]{4,5}title">([^<]*)</span>')
    # poster email
    email_regex = re.compile(r'<a href="mailto:([^"]*)" class="linkmail">')
    # poster comment
    comment_regex = re.compile(r'<blockquote>(.*?)</blockquote>', re.S)
    # double dash (thread post splitter)
    doubledash_regex = re.compile(r'<td nowrap class="doubledash">&gt;&gt;</td>')
    # no week day time hack regex
    noweekday_regex = re.compile(r'\([a-zA-Z]{3,3}?\)')
    
    def __init__(self, url):
        self.url = url
        self.page_time = None
        self.posts = {}
        self.is_source = False
        self.ignore = False
        self.need_update = False
    
    def update(self):
        html, self.page_time = openurl(self.url, self.page_time)
        if html is None:
            return False
        t_area = re.search(r'<form name="delform" action="[^"]*" method=POST>(.*?)</form>', html, re.S).group(1)
        return self.update_from_text(t_area)
    
    def update_from_text(self, t_area):
        added, not_added = 0, 0
        for p in self.doubledash_regex.split(t_area):
            name, trip, time, id = self.post_header_regex.search(p).groups()
            if id not in self.posts: # only parse this post if we don't already have it
                comment = self.comment_regex.search(p).group(1)
                email = self.email_regex.search(p)
                if email is not None:
                    email = email.group(1)
                subject = self.subject_regex.search(p).group(1)
                img = self.img_regex.search(p)
                if img is not None:
                    img = img.groups()
                p = self.posts[id] = {
                    'id':id,
                    'subject':subject,
                    'name':name,
                    'trip':trip,
                    'time':time,
                    'comment':comment,
                    'email':email,
                    'has_img':False}
                if img is not None:
                    #print img
                    p['has_img'] = True
                    p['img_name'] = img[0]
                    p['img_size'] = img[1]
                    p['img_w'] = int(img[2].split('x')[0])
                    p['img_h'] = int(img[2].split('x')[1])
                    p['img_url'] = img[3]
                    p['img_thumburl'] = img[4]
                added += 1
            else:
                not_added += 1
        return added, not_added
    
    def sorted_posts(self):
        result = self.posts.values()
        result.sort(key=lambda p: p['id'])
        return result
    
    def get_bump_time(self):
        bump_post = self.sorted_posts()[-1]
        bump_time = bump_post['time'].strip()
        if bump_time == '':
           # print BUMPTIME_EMPTY_VAL # for testing
            return BUMPTIME_EMPTY_VAL
        else:
            bump_time = re.sub(self.noweekday_regex, '', bump_time) # removes the weekday so locales won't fail
            #print bump_time # for testing
            return time.strptime(bump_time, '%m/%d/%y%H:%M') 



class DLManagerDialog(wx.Dialog):
    def __init__(self, parent):
        import wx.lib.scrolledpanel as scrolled
        wx.Dialog.__init__(self, parent, title='Download Manager', size=(800,600), style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)
        self.parent = parent
        
        self.sizer_all = sizer_all = wx.BoxSizer(wx.VERTICAL)
        self.sizer_main = sizer_main = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer_buttons = sizer_buttons = wx.BoxSizer(wx.HORIZONTAL)
        
        self.source_box = source_box = wx.ListBox(self, -1, size=(100,-1), choices=board_names)
        #source_box.Bind(wx.EVT_CHECKLISTBOX, self.SourceCheckListBox)
        source_box.Bind(wx.EVT_LISTBOX, self.SourceListBox)
        
        self.thread_panel = thread_panel = scrolled.ScrolledPanel(self)
        self.sizer_thread = wx.BoxSizer(wx.VERTICAL)
        thread_panel.SetSizer( self.sizer_thread )
        thread_panel.SetAutoLayout(1)
        thread_panel.SetupScrolling()
        
        sizer_main.Add(source_box, 0, wx.EXPAND)
        sizer_main.Add(thread_panel, 1, wx.EXPAND)
        
        self.b_select_all = b_select_all = wx.Button(self, -1, "Select All")
        self.b_select_none = b_select_none = wx.Button(self, -1, "Select None")
        
        sizer_buttons.Add(b_select_all, 0, wx.EXPAND)
        sizer_buttons.Add(b_select_none, 0, wx.EXPAND)
        
        sizer_all.Add(sizer_main, 1, wx.EXPAND)
        sizer_all.Add(sizer_buttons, 0, wx.EXPAND)
        
        b_select_all.Bind(wx.EVT_BUTTON, self.OnSelectAll)
        b_select_none.Bind(wx.EVT_BUTTON, self.OnSelectNone)
        
        self.SetSizer(sizer_all)
        self.panel_threads = []
    
    def OnSelectAll(self, event):
        for thread_panel in self.panel_threads:
            obj = thread_panel.actual_thread_obj
            if not obj.ignore:
                obj.is_source = True
                thread_panel.thread_panel_check.SetValue(True)
    
    def OnSelectNone(self, event):
        for thread_panel in self.panel_threads:
            thread_panel.actual_thread_obj.is_source = False
            thread_panel.thread_panel_check.SetValue(False)
        
    def SourceCheckListBox(self, e):
        index = e.GetSelection()
        label = self.source_box.GetString(index)
        checked = self.source_box.IsChecked(index)
        if checked:
            can_select = self.UpdateBoard(label)
            if not can_select:
                self.source_box.SetChecked(index, False)
            else:
                self.SelectBoard(label)
    
    def SourceListBox(self, e):
        label = e.GetString()
        #self.SetAutoLayout(True)
        can_select = self.UpdateBoard(label)
        if can_select:
            self.SelectBoard(label)
    
    def SelectBoard(self, label):
        # make sure thumbs directory exists
        if not os.path.isdir(thumb_cache):
            os.mkdir(thumb_cache)
        
        class GoddamnButton(object):
            def __init__(self, check, thread):
                self.check = check
                self.thread = thread
            def __call__(self, event):
                self.thread.is_source = self.check.IsChecked()
        
        class GoddamnIgnoreButton(object):
            def __init__(self, check, thread):
                self.check = check
                self.thread = thread
            def __call__(self, event):
                self.thread.ignore = self.check.IsChecked()
        
        import cStringIO
        if label in self.source_box.GetStrings() and label in self.parent.board_downloaders:
            b = self.parent.board_downloaders[label]
            for n in self.panel_threads: n.Destroy()
            self.panel_threads = []
            self.sizer_thread.Clear()
            self.thread_panel.Show(False)
            cflip = 0
            sorted_threads = b.threads.items()
            sorted_threads.sort(key=lambda i: i[1].get_bump_time())
            sorted_threads.reverse()
            sorted_threads.sort(key=lambda i: i[1].ignore) # push ignored threads to end of list
            if filter(lambda a: not hasattr(a, 'thumb_bmp'), sorted_threads):
                
                # figure out which to get
                to_grab = []
                for i, v in enumerate(sorted_threads):
                    t_key, thread = v
                    op_post = thread.sorted_posts()[0]
                    
                    # filter out thumbnails for spam posts
                    skip_thread = False
                    for spam_filter in spam_filters:
                        if re.search(spam_filter, op_post['comment']):
                            skip_thread = True
                            break
                    if skip_thread:
                        continue
                    
                    if 'img_thumburl' not in op_post:
                        pass
                    elif not hasattr(thread, 'thumb_bmp'):
                        op_thumb_url = op_post['img_thumburl']
                        to_grab.append((thread, op_thumb_url))
                
                # get the ones we need
                progress = wx.ProgressDialog(
                                "Loading Thumbnails",
                                'Loading thumbnails for /'+label+'/',
                                maximum=len(to_grab),
                                parent=self,
                                style=wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_ESTIMATED_TIME | wx.PD_REMAINING_TIME
                            )
                #for i, v in enumerate(to_grab):
                needed = len(to_grab)
                max_get = 8
                cur_get = []
                while to_grab or cur_get:
                    progress.Update(min(needed - 1,needed - len(to_grab)))
                    while len(cur_get) < max_get and to_grab:
                        thread, thumb_url = to_grab.pop(0)
                        thumb_path = os.path.join(thumb_cache, thumb_url.rsplit('/', 1)[-1])
                        if os.path.isfile(thumb_path):
                            f = open(thumb_path, 'rb')
                            thumb_dat = f.read()
                            f.close()
                            stream = cStringIO.StringIO(thumb_dat)
                            thread.thumb_bmp = wx.BitmapFromImage(wx.ImageFromStream(stream))
                        else:
                            getter = OpenUrlThreaded(thumb_url)
                            getter.start() # begin the thread
                            cur_get.append((thread, getter))
                    for bleh in cur_get[:]:
                        thread, getter = bleh
                        if getter.result:
                            thumb_dat, mod_time = getter.result
                            
                            # restart if the connection was lost
                            if thumb_dat == 504:
                                op_post = thread.sorted_posts()[0]
                                thumb_url = op_post['img_thumburl']
                                getter = OpenUrlThreaded(thumb_url)
                                getter.start() # begin the thread
                                cur_get.append((thread, getter))
                            
                            # only grab the file if it still exists
                            elif thumb_dat != 404:
                                # write to thumb cache
                                op_post = thread.sorted_posts()[0]
                                thumb_url = op_post['img_thumburl']
                                thumb_path = os.path.join(thumb_cache, thumb_url.rsplit('/', 1)[-1])
                                try:
                                    f = None
                                    f = open(thumb_path, 'wb')
                                    f.write(thumb_dat)
                                finally:
                                    if f is not None: f.close()
                                # turn into bitmap
                                stream = cStringIO.StringIO(thumb_dat)
                                thread.thumb_bmp = wx.BitmapFromImage(wx.ImageFromStream(stream))
                            
                            cur_get.remove(bleh)
                    time.sleep(0.25)
                progress.Destroy()
                    
            for i, v in enumerate(sorted_threads):
                t_key, thread = v
                # basic setup
                op_post = thread.sorted_posts()[0]
                
                # filter out all that goddamn SPAM
                skip_thread = False
                for spam_filter in spam_filters:
                    if re.search(spam_filter, op_post['comment']):
                        skip_thread = True
                        break
                if skip_thread:
                    continue
                
                # create a panel for this thread
                n = wx.Panel(self.thread_panel)
                n.actual_thread_obj = thread
                n_sizer = wx.BoxSizer(wx.VERTICAL)
                # force scroll focusing
                n.force_scrolling = wx.Panel(n, -1, size=(0,0))
                n_sizer.Add(n.force_scrolling)
                class damnit(object):
                    def __init__(self, bleh):
                        self.bleh = bleh
                    def __call__(self, e):
                        if isinstance(self.bleh.FindFocus(), (wx.TextCtrl, wx.ListBox)):
                            self.bleh.SetFocus()
                n.Bind(wx.EVT_ENTER_WINDOW, damnit(n.force_scrolling))
                
                n_sizer.Add((5,10)) # a little bit of padding
                
                # download checkbox
                check = wx.CheckBox(n, -1, "Download images from this thread")
                if thread.is_source:
                    check.SetValue(True)
                check.Bind(wx.EVT_CHECKBOX, GoddamnButton(check, thread))
                n_sizer.Add(check, 0)
                n.thread_panel_check = check
                
                n_sizer.Add((5,8)) # a little bit of padding
                
                # content sizer
                content_sizer = wx.BoxSizer(wx.HORIZONTAL)
                content_sizer2 = wx.BoxSizer(wx.VERTICAL)
                
                # thumb display
                #op_thumb_url = op_post['img_thumburl']
                if hasattr(thread, 'thumb_bmp'):
                    bmp = thread.thumb_bmp
                    thumb_bmp = wx.StaticBitmap(n, -1, bmp)
                    content_sizer.Add(thumb_bmp, 0)
                
                title_sizer = wx.BoxSizer(wx.HORIZONTAL)
                font = wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
                if op_post['subject']:
                    # subject
                    t = html_to_text(op_post['subject']).decode("utf-8", "replace")
                    subject = wx.StaticText(n, -1, t)
                    subject.SetFont(font)
                    subject.SetForegroundColour((204,17,5))
                    #content_sizer2.Add(subject)
                    title_sizer.Add(subject)
                
                if op_post['name']:
                    # poster name
                    op_name_text = html_to_text(' '+op_post['name']).decode("utf-8", "replace")
                    op_name = wx.StaticText(n, -1, op_name_text)
                    op_name.SetFont(font)
                    op_name.SetForegroundColour((17,119,67))
                    title_sizer.Add(op_name)
                '''
                if op_post['trip'] is not None:
                    op_name_text += ' '+html_to_text(op_post['trip']).decode("utf-8", "replace")
                '''
                content_sizer2.Add(title_sizer)
                
                
                try: # 240, 224, 214 # 255,255,238
                    t = html_to_text(op_post['comment']).decode("utf-8", "replace")
                    text = wx.TextCtrl(n, -1, t, style=wx.TE_READONLY|wx.TE_AUTO_URL|wx.TE_MULTILINE|wx.TE_RICH|wx.NO_BORDER)
                    text.SetForegroundColour((128,0,0))
                    if thread.ignore:
                        text.SetBackgroundColour((111,111,128+(32<<cflip)))
                    elif cflip:
                        text.SetBackgroundColour((240,224,214))
                    else:
                        text.SetBackgroundColour((255,255,238))
                    #text = wx.StaticText(n, -1, t_key+'\n'+t)
                    content_sizer2.Add(text, 0, wx.EXPAND)
                except:
                    print 'can\'t decode unicode text for post:\n',t
                    raise
                
                content_sizer.Add(content_sizer2, 1, wx.EXPAND)
                n_sizer.Add(content_sizer, 0, wx.EXPAND)
                
                n_sizer.Add((5,8)) # a little bit of padding
                
                # ignore checkbox
                ignore = wx.CheckBox(n, -1, "Ignore this thread (push to end of list next time this board is opened, and won't be affected by Select All)")
                if thread.ignore:
                    ignore.SetValue(True)
                ignore.Bind(wx.EVT_CHECKBOX, GoddamnIgnoreButton(ignore, thread))
                n_sizer.Add(ignore, 0)
                n.thread_panel_ignore = ignore
                
                n_sizer.Add((5,10)) # a little bit of padding
                
                if thread.ignore:
                    n.SetBackgroundColour((111,111,128+(32<<cflip)))
                elif cflip:
                    n.SetBackgroundColour((240,224,214))
                else:
                    n.SetBackgroundColour((255,255,238))
                cflip^=1
                n.SetSizer(n_sizer)
                self.sizer_thread.Add(n, 0, wx.EXPAND)
                self.panel_threads.append(n)
            self.thread_panel.SetSizer(self.sizer_thread)
            self.thread_panel.Layout()
            self.thread_panel.SetupScrolling()
            self.thread_panel.Show(True)
            self.thread_panel.Layout()
        else:
            print '???'
    
    def UpdateBoard(self, label):
        # add the board if it doesn't already exist
        if label not in self.parent.board_downloaders:
            self.parent.board_downloaders[label] = ChanBoard(label)
        b = self.parent.board_downloaders[label]
        
        progress = None
        brokeout = False
        
        #'''
        if b.pages is None:
            #cur_pos = 0
            max_requests = 8
            cur_requests = []
            detected_end = None
            for i in xrange(max_requests):
                r_thread = ThreadedResult(b.update_page, i)
                r_thread.start()
                cur_requests.append((i, r_thread))
            while b.pages is None or None in b.page_time:
                if None in b.page_time and len(cur_requests) < max_requests:
                    for i, v in enumerate(b.page_time):
                        if v is None:
                            # now check to make sure it isn't already being requested
                            doing_it = False
                            for req in cur_requests:
                                if req[0] == i:
                                    doing_it = True
                                    break
                            if not doing_it:
                                r_thread = ThreadedResult(b.update_page, i)
                                r_thread.start()
                                cur_requests.append((i, r_thread))
                # remove completed requests
                for req in cur_requests[:]:
                    if req[1].result is not None:
                        cur_requests.remove(req)
                # make a progress dialog if we need one
                if progress is None and b.pages is not None:
                    progress = wx.ProgressDialog(
                                    "Getting Board Data",
                                    'Getting list of threads from /'+label+'/',
                                    maximum=b.pages,
                                    parent=self,
                                    style=
                                        wx.PD_CAN_ABORT | 
                                        wx.PD_ELAPSED_TIME | 
                                        wx.PD_ESTIMATED_TIME | 
                                        wx.PD_REMAINING_TIME |
                                        wx.PD_AUTO_HIDE
                                )
                # allow breakout from the update
                if progress is not None:
                    keepgoing, skip = progress.Update(len(filter(lambda a: a is not None, b.page_time)))
                    if not keepgoing:
                        brokeout = True
                        break
                time.sleep(0.1)
        else:
            for i, v in enumerate(b.update_iter()):
                changed_t, same_t = v
                if ((changed_t and not same_t) or not changed_t) and None not in b.page_time:
                    break # everything is current
                if progress is None:
                    progress = wx.ProgressDialog(
                                    "Getting Board Data",
                                    'Getting list of threads from /'+label+'/',
                                    maximum=b.pages,
                                    parent=self,
                                    style=
                                        wx.PD_CAN_ABORT | 
                                        wx.PD_ELAPSED_TIME | 
                                        wx.PD_ESTIMATED_TIME | 
                                        wx.PD_REMAINING_TIME |
                                        wx.PD_AUTO_HIDE
                                )
                keepgoing, skip = progress.Update(i)
                if not keepgoing:
                    brokeout = True
                    break
        if progress is not None:
            progress.Destroy()
        if brokeout:
            return False
        return True




class ImageData(object):
    def __init__(self, path):
        self.path = path # does not include path
        self.basename = os.path.basename(path)
        self.dirname = os.path.dirname(path)
        self.should_show = True
        self.show_count = 0
        
        self.count = None
        self.speed = None
        self.intensity = None
        self.blacklisted = None



class ImageManager(object):
    def __init__(self):
        self.files = []
        self.playdata = {}
        self.cur_bitmap = []
        self.fs_bitmap = []
        self.cur_animated = False
        self.cur_ani_index = 0
        self.ani_counter = 0
        #self.show_count = []
        self.cur_image_path = None
        self.image_history = []
        self.image_data = {}
        self.scale_enabled = True
        self.folders = ['cache/']
        self.paused = False
        self.auto_advance = True
        self.last_pause_time = None
        self.fullscreen = False
        
        # fap frenzy
        self.additional_rate = 0.0
        self.additional_rate_inc = 0.1
        self.use_additional_rate = False
        
        # "I came" stuff
        self.last_time = None
        self.last_stroke_number = 0
        self.intensity_image_count = {}
        
        # load up defaults
        self.load_display_data()
        self.load_folder_cfg()
        
        # test
        for g in self.folders:
            self.add_folder_images(g)
        self.switch_image()
        
    def load_folder_cfg(self, fn=None):
        if fn is None:
            fn = 'folders.cfg'
        try:
            f = None
            f = open(fn)
            for dir in f.read().splitlines():
                if dir not in self.folders:
                    self.folders.append(dir)
        except:
            pass
        finally:
            if f is not None:
                f.close()
    
    def save_folder_cfg(self, fn=None):
        if fn is None:
            fn = 'folders.cfg'
        try:
            f = None
            f = open(fn, 'w')
            n = dict.fromkeys(str(i) for i in self.folders).keys()
            f.write('\n'.join(n))
        except:
            pass
        finally:
            if f is not None:
                f.close()
    
    def load_display_data(self, fn=None):
        if fn is None:
            fn = 'dispdata.cfg'
        if os.path.exists(fn) and os.path.isfile(fn):
            f_got = None
            try:
                f = None
                f = open(fn)
                f_got = f.read()
            except:
                pass
            finally:
                if f is not None:
                    f.close()
            if f_got is not None:
                lines = f_got.splitlines()
                pd = None
                for line in lines:
                    if ':' in line:
                        head, tail = line.split(':', 1)
                        if head == 'file':
                            self.playdata[tail] = pd = {}
                        elif pd is not None:
                            if head == 'count' and tail.isdigit():
                                pd['count'] = int(tail)
                            else:
                                pd[head] = tail
    
    def save_display_data(self, fn=None):
        if fn is None:
            fn = 'dispdata.cfg'
        s = ''
        for imgdata in self.image_data.values():
            bn = imgdata.basename
            if imgdata.count is not None:
                if bn not in self.playdata:
                    self.playdata[bn] = {'count':imgdata.count}
                else:
                    self.playdata[bn]['count'] = imgdata.count
            if imgdata.speed is not None:
                if bn not in self.playdata:
                    self.playdata[bn] = {'speed':imgdata.speed}
                else:
                    self.playdata[bn]['speed'] = imgdata.speed
            if imgdata.intensity is not None:
                if bn not in self.playdata:
                    self.playdata[bn] = {'intensity':imgdata.intensity}
                else:
                    self.playdata[bn]['intensity'] = imgdata.intensity
            if imgdata.blacklisted is not None:
                if bn not in self.playdata:
                    self.playdata[bn] = {'blacklisted':imgdata.blacklisted}
                else:
                    self.playdata[bn]['blacklisted'] = imgdata.blacklisted
        for key in self.playdata:
            s += 'file:'+key+'\n'
            for k,v in self.playdata[key].items():
                s += k+':'+str(v)+'\n'
            s += '\n'
        try:
            f = None
            f = open(fn, 'w')
            f.write(s)
        except:
            pass
        finally:
            if f is not None:
                f.close()
    
    def switch_image(self, imagepath=None):
        if self.cur_image_path is not None and imagepath is None:
            # only push image onto history if autoadvancing or forward key was
            # pressed
            self.image_history.append(self.cur_image_path)

        if imagepath is None:
            a = self.image_data.keys()
            if a:
                if 1: # semi-random
                    l = self.image_data.items()
                    l.sort(key=lambda a: a[1].show_count)
                    l = filter(lambda a: a[1].show_count == l[0][1].show_count, l)
                    imagepath = l[randint(0, len(l)-1)][0]
                    
                    # try to avoid showing the same image twice in a row
                    if imagepath == self.cur_image_path:
                        for i in l:
                            if i is not imagepath:
                                switched = self.switch_image(i[0])
                                if switched:
                                    return switched
                else: # ordered
                    a.sort()
                    b = 0
                    if self.cur_image_path is not None:
                        if self.cur_image_path in a:
                            b = (a.index(self.cur_image_path) + 1) % len(a)
                    imagepath = a[b]
            else:
                return False
        
        if self.image_data[imagepath].blacklisted is not None:
            self.image_data[imagepath].show_count += 50
            #del self.image_data[imagepath]
            return False
        
        # make sure the image exists
        if not os.path.exists(imagepath):
            #if imagepath in self.image_data:
            #    del self.image_data[imagepath]
            self.image_data[imagepath].show_count += 50
            return False
        
        # make sure the image data is stored
        if imagepath not in self.image_data:
            self.add_image_data(imagepath)
        
        # load the image
        if imagepath[-4:] == '.gif':
            try:
                ani = wx.animate.Animation(imagepath)
            except:
                self.image_data[imagepath].show_count += 50
                return False
            self.cur_animated = True
            self.cur_ani_index = 0
            self.ani_counter = 0
            self.cur_bitmap = []
            ani_size = ani.GetSize()
            current = wx.EmptyBitmap(ani_size[0], ani_size[1])
            memory_dc = wx.MemoryDC()
            memory_dc.SelectObject(current)
            for i in xrange(ani.GetFrameCount()):
                ani_bmp = wx.BitmapFromImage(ani.GetFrame(i))
                px, py = ani.GetFramePosition(i)
                memory_dc.DrawBitmap(ani_bmp, px, py, 1)
                
                # Seems that 0.03 is the longest animation delay any browser uses:
                
                # Safari:  (< 0.03) -> 0.03 (not so bad)
                # Firefox: (< 0.02) -> 0.10 (make sense)
                # IE:      (< 0.06) -> 0.10 (make NO sense, 0.7 renders faster than 0.6?)
                # Opera:   (< 0.10) -> 0.10 (consistently bad)
                # Google Chrome is probably the same as Safari, they both use WebKit for rendering
                
                # From looking at a buncha gifs,
                # it seems that a delay of 0 indicates that it expects a delay of 0.10.
                # Standard video rate is about 60hz, so we'll cap to 0.016
                
                delay = ani.GetDelay(i)
                delay = delay and max(16, delay) or 100
                self.cur_bitmap.append((wx.BitmapFromImage(wx.Bitmap.ConvertToImage(current)), delay))
            memory_dc.SelectObject(wx.NullBitmap)
            self.last_ani_time = int(time.time() * 1000)
            timelen = sum([n[1] for n in self.cur_bitmap])/1000.0
            print 'Anim time:',timelen,'Recommended speed:',1/max(0.016, timelen),'* strokes'
        else:
            try:
                n = wx.Bitmap(imagepath)
            except:
                self.image_data[imagepath].show_count += 50
                return False
            self.cur_animated = False
            self.cur_ani_index = 0
            self.cur_bitmap = [(n, 0)]
        
        # clear the fullscreen bitmap
        self.fs_bitmap = []
        
        imgdata = self.image_data[imagepath]
        
        self.cur_image_path = imagepath
        self.cur_image_start_time = time.time()
        
        if imgdata.intensity is not None:
            self.cur_intensity = imgdata.intensity
        else:
            intense = intensities[randint(0,len(intensities)-1)]
            self.cur_intensity = intense
        
        if imgdata.speed is None:
            if self.cur_animated:
                anim_rate = 1 / timelen
                if timelen < 2.5:
                    rate = anim_rate
                else:
                    # todo: figure out a better way of auto-detecting strokes
                    rate = anim_rate * randint(3, int(timelen+1))
            else:
                rate = randint(300,4500)/1000.0
        else:
            try:
                rate = float(imgdata.speed)
            except ValueError:
                rate = 1.0 # TODO fix this
        self.cur_rate = rate
        
        if imgdata.count is None:
            if rate < 1:
                self.cur_count = randint(10,30)
            elif rate < 2:
                self.cur_count = randint(15,70)
            elif rate < 3:
                self.cur_count = randint(20,110)
            elif rate < 4:
                self.cur_count = randint(25,140)
            else:
                self.cur_count = randint(30,170)
        else:
            self.cur_count = int(imgdata.count)
        
        # increment the count of how many times this image has been shown
        self.image_data[imagepath].show_count += 1
        
        # fap frenzy
        if self.use_additional_rate:
            self.additional_rate += self.additional_rate_inc
            self.cur_rate += self.additional_rate
        
        # "I came" stuff
        if self.cur_intensity not in self.intensity_image_count:
            self.intensity_image_count[self.cur_intensity] = [1, 0, 0] # imgs, stroke, time
        else:
            self.intensity_image_count[self.cur_intensity][0] += 1
        return True
    
    def update_anim(self, amount):
        if self.cur_animated:
            if self.cur_bitmap[self.cur_ani_index][1] < 1:
                self.ani_counter = 0
                self.cur_ani_index = (self.cur_ani_index + 1) % len(self.cur_bitmap)
            else:
                self.ani_counter += amount
                if self.ani_counter > self.cur_bitmap[self.cur_ani_index][1]:
                    self.ani_counter -= self.cur_bitmap[self.cur_ani_index][1]
                    self.cur_ani_index = (self.cur_ani_index + 1) % len(self.cur_bitmap)
        else:
            self.cur_ani_index = 0
    
    def show_image(self, parent):
        if self.cur_animated:
            t = int(time.time() * 1000)
            n = t - self.last_ani_time
            self.last_ani_time = t
            if not self.paused:
                self.update_anim(n)
        else:
            self.cur_ani_index = 0
        # set up the drawing context
        dc = wx.BufferedPaintDC(parent)
        dcw, dch = parent.GetClientSize()
        
        # clear to black
        dc.SetBrush(wx.Brush(wx.BLACK))
        dc.SetPen(wx.Pen(wx.BLACK, 1))
        dc.DrawRectangle(0, 0, dcw, dch)
        
        if self.cur_bitmap:
            # get the image bitmap
            bmp = self.cur_bitmap[self.cur_ani_index][0]
            # get the image size
            iw, ih = bmp.GetSize()
            
            # draw the image/animation (and maybe scale to fit)
            if not self.scale_enabled:
                dc.DrawBitmap(bmp, (dcw-iw)/2, (dch-ih)/2)
            else:
                w_ratio = float(dcw) / max(1,iw)
                h_ratio = float(dch) / max(1,ih)
                if w_ratio < h_ratio:
                    x, y, w, h = 0, (dch-ih*w_ratio)/2, dcw, ih*w_ratio
                else:
                    x, y, w, h = (dcw-iw*h_ratio)/2, 0, iw*h_ratio, dch
                
                if self.fullscreen:
                    if not self.fs_bitmap:
                        self.fs_bitmap = [None] * len(self.cur_bitmap)
                    if self.fs_bitmap[self.cur_ani_index] is None:
                        current = wx.EmptyBitmap(w, h)
                        memory_dc = wx.MemoryDC()
                        memory_dc.SelectObject(current)
                        memgc = wx.GraphicsContext.Create(memory_dc)
                        memgc.DrawBitmap(bmp, 0, 0, w, h)
                        memory_dc.SelectObject(wx.NullBitmap)
                        self.fs_bitmap[self.cur_ani_index] = current
                        del memory_dc, memgc, current
                    if bmp.IsOk():
                        bmp = self.fs_bitmap[self.cur_ani_index]
                        dc.DrawBitmap(bmp, x, y)
                    else: # no idea why this would happen, but alright
                        self.fs_bitmap[self.cur_ani_index] = None
                        gc = wx.GraphicsContext.Create(dc)
                        gc.DrawBitmap(bmp, x, y, w, h)
                else:
                    gc = wx.GraphicsContext.Create(dc)
                    gc.DrawBitmap(bmp, x, y, w, h)
            
            if self.paused:
                # draw pause string
                dc.SetFont(wx.Font(35, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                tx, ty = 0, dch/2
                dc.DrawText("Paused", tx+1, ty)
                dc.DrawText("Paused", tx-1, ty)
                dc.DrawText("Paused", tx, ty+1)
                dc.DrawText("Paused", tx, ty-1)
                dc.SetTextForeground((255, 255, 255))
                dc.DrawText("Paused", tx, ty)

                # timing stuff
                if self.last_pause_time is not None:
                    self.cur_image_start_time += time.time() - self.last_pause_time
                self.last_pause_time = time.time()
                self.last_time = None
            else:
                self.last_pause_time = None
        
                # keep time count for "I came"
                if self.last_time is None:
                    self.last_time = time.time()
                else:
                    self.intensity_image_count[self.cur_intensity][2] += time.time() - self.last_time
                    self.last_time = time.time()
            
            t_count = time.time() - self.cur_image_start_time
            count = int(self.cur_rate * t_count)
            t_period = (1 / self.cur_rate)
            pos = (t_count % t_period) * self.cur_rate
            
            # "I came" stroke count
            if self.last_stroke_number != count:
                self.intensity_image_count[self.cur_intensity][1] += 1
                self.last_stroke_number = count
            
            # text stuff
            if 1:
                c = 127-cos(radians(pos*360))*128
            else:
                c = (pos > 0.5) * 255
                
            dc.SetFont(wx.Font(35, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            
            self.text = str(max(0, self.cur_count - count)) +', '+ self.cur_intensity
            
            tw, th = dc.GetTextExtent(self.text)
            tx, ty = (dcw-tw)/2, 0
            
            inv_c = 0 #(255-c)/2
            dc.SetTextForeground((inv_c, inv_c, inv_c))
            dc.DrawText(self.text, tx+1, ty)
            dc.DrawText(self.text, tx-1, ty)
            dc.DrawText(self.text, tx, ty+1)
            dc.DrawText(self.text, tx, ty-1)
            dc.SetTextForeground((c, 0, c))
            dc.DrawText(self.text, tx, ty)#, dch-th)# 0,0)#
            
            # auto advancement
            if self.auto_advance and count == self.cur_count:
                for i in self.image_data:
                    switched = self.switch_image()
                    if switched:
                        break

        else:
            dc.SetFont(wx.Font(35, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.SetTextForeground((200, 200, 200))
            dc.DrawText("No images cached yet", 0, 0)
            for i in self.image_data:
                switched = self.switch_image()
                if switched:
                    break

    def add_image_data(self, path, extra_data=None):
        if path not in self.image_data:
            self.image_data[path] = ImageData(path)
        imgdat = self.image_data[path]
        if imgdat.basename in self.playdata:
            pd = self.playdata[imgdat.basename]
            if 'count' in pd:
                imgdat.count = pd['count']
            if 'speed' in pd:
                imgdat.speed = pd['speed']
            if 'intensity' in pd:
                imgdat.intensity = pd['intensity']
            if 'blacklisted' in pd:
                imgdat.blacklisted = pd['blacklisted']
        elif extra_data is not None:
            imgdat.count, imgdat.speed, imgdat.intensity = extra_data
    
    def add_folder_images(self, path):
        if os.path.isdir(path):
            for n in os.listdir(path):
                m = os.path.join(path, n)
                if os.path.isfile(m):
                    if os.path.splitext(m)[1] in ('.gif', '.jpg', '.bmp', '.png'):
                        self.add_image_data(m)
    
    def rem_folder_images(self, path):
        if os.path.isdir(path):
            if path[-1] in ('\\', '/'):
                path = os.path.dirname(path)
            for i in self.image_data.keys():
                if os.path.dirname(i) == path:
                    del self.image_data[i]





class DownloadManager(threading.Thread):
    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.parent = parent
        #self.img_getter = RandomThreadImage()
        self.new_cached = []
        self.new_cached_lock = threading.Lock()
        self.min_refresh_delay = 45
        self.max_refresh_delay = 120
        self.last_full_refresh = time.time()
    
    def run(self):
        while 1:
            #sleep = 2.5
            sleep = 0.0
            need_refresh = False
            try:
                if self.parent.download_enabled and len(self.new_cached) < 50:
                    sleep = 0.0
                    threads = []
                    for b in self.parent.board_downloaders.values():
                        threads.extend(filter(lambda t: t.is_source, b.threads.values()))
                    image_posts = []
                    for t in threads:
                        if t.need_update:
                            t.update()
                            t.need_update = False
                        image_posts.extend(filter(lambda p: 'img_url' in p, t.posts.values()))
                    to_get = []
                    pd = self.parent.image_manager.playdata
                    for img_post in image_posts:
                        image_base = img_post['img_url'].rsplit('/', 1)[-1]
                        if image_base not in os.listdir(cache_dir):
                            if image_base in pd and 'blacklisted' in pd[image_base]:
                                pass # don't grab blacklisted files
                            elif self.parent.gif_only_mode and image_base[-4:] != '.gif':
                                pass # don't grab anything but gifs in gif mode
                            else:
                                to_get.append(img_post)
                    if to_get:
                        which = to_get[randint(0, len(to_get) - 1)]
                        comment = html_to_text(which['comment'])
                        extra_data = None
                        
                        meh = re.search(r'(\d+)[ \t]*([,\\/])(.*)', comment)
                        if meh is not None:
                            force_doubles = 'medium', 'normal'
                            speed_map = {
                                'extremely slow':0.25,
                                'very slow':0.333,
                                'slow':0.5,
                                'medium':1.0,
                                'normal':1.0,
                                'fast':2.0,
                                'very fast':3.0,
                                'extremely fast':4.0
                            }
                            same_as_pic_texts = [
                                'speed', 'pace', 'same as'
                            ]
                            
                            detected_count, separator, rest = meh.groups()
                            detected_speed = None
                            detected_force = None
                            speed_index = None
                            line = rest.split('\n')[0]
                            parts = line.split(separator)
                            
                            # find the speed
                            for i, v in enumerate(parts):
                                # if it's "same as gif" or whatever, auto-detect speed
                                for sapt in same_as_pic_texts:
                                    if sapt in v.lower().strip():
                                        speed_index = i
                                        break
                                # if we already have a speed, we don't have to look further
                                if speed_index is not None:
                                    break
                            
                            # find the speed (if auto-pacing didn't find it)
                            for i, v in enumerate(parts):
                                # if we already have a speed, we don't have to look further
                                if speed_index is not None:
                                    break
                                # "fast", "slow", "medium", etc.
                                if v.lower().strip() in speed_map:
                                    detect_double = False
                                    # make sure "medium, slow" doesn't get detected as speed=medium, force=slow
                                    for j, to_check in enumerate(parts[i:]):
                                        if j == i:
                                            continue
                                        if to_check in speed_map and to_check not in force_doubles:
                                            detect_double = True
                                            break
                                    if not detect_double:
                                        detected_speed = speed_map[v.lower().strip()]
                                        speed_index = i
                                        continue # got a named speed
                                num = re.search(r'(\d+(?:.\d+)?)', v)
                                if num is not None:
                                    detected_speed = float(num.group(1))
                                    speed_index = i
                                    continue # got a float speed
                            
                            # if we got a speed, find the force
                            if speed_index is not None:
                                # if the speed is at the begining, use everything after it for the force
                                if speed_index == 0:
                                    detected_force = separator.join(parts[1:])
                                # otherwise, grab everything in the middle
                                else:
                                    detected_force = separator.join(parts[:speed_index])
                            # if we didn't find a speed, try to find a force anyway
                            else:
                                force_index = None
                                for i, v in enumerate(parts):
                                    for intensity in intensities:
                                        if intensity in v.lower().strip():
                                            force_index = i
                                            detected_force = v
                                            break
                                    if force_index:
                                        break
                            
                            
                            # scan the comment text for a specific speed
                            all_lines = comment.splitlines()
                            for l in all_lines:
                                num = re.match(r'\s*\(\s*(\d+(?:.\d+)?)\s*\)', l)
                                if num is not None:
                                    detected_speed = float(num.group(1))
                                    break
                            
                            # even if we don't have a force or speed, we at least have a count
                            extra_data = detected_count, detected_speed, detected_force
                        # locking would be useful here
                        imgurl = which['img_url']
                        print "Downloading " + imgurl + " ...",
                        got, mod_time = openurl(imgurl)
                        image_base = imgurl.rsplit('/', 1)[-1]
                        img_cache_path = cache_dir + image_base
                        if got != 404 and got is not None:
                            f = open(img_cache_path, 'wb')
                            f.write(got)
                            f.close()
                            self.new_cached.append((img_cache_path, extra_data))
                            print "success"
                    else:
                        need_refresh = True
                        sleep = 0.5
                last_refresh = time.time() - self.last_full_refresh
                if not need_refresh and last_refresh > self.max_refresh_delay:
                    sleep = 0.0
                    for b in self.parent.board_downloaders.values():
                        b.update()
                    self.last_full_refresh = time.time()
                if need_refresh and last_refresh > self.min_refresh_delay:
                    sleep = 0.0
                    for b in self.parent.board_downloaders.values():
                        b.update()
                    self.last_full_refresh = time.time()

            except wx.PyDeadObjectError:
                exit()
            except:
                import traceback
                print 'Error in Download Management Thread, attempting to recover'
                traceback.print_exc()
                sleep = 5.0
            if sleep:
                time.sleep(sleep) # wait a bit
    
    def get_new_cached(self):
        self.new_cached_lock.acquire()
        result, self.new_cached = self.new_cached, []
        self.new_cached_lock.release()
        return result



class MainFrame(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title, size=(800,600))
        self.SetDoubleBuffered(True)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.board_downloaders = {}
        self.download_enabled = True
        self.gif_only_mode = False
        self.refresh_timer = wx.CallLater(100, self.Refresh)
        self.mouse_timer = None
        self.key_state = False
        self.fap_frenzy = False
        
        self.image_manager = ImageManager()
        self.download_manager = DownloadManager(self)
        self.download_manager.start()
        
        # basic prep
        self.SetBackgroundColour((0,0,34))
        self.Centre()
        
        # set up the menu
        self.menu = wx.Menu()
        
        self.menu_scale_id = wx.NewId()
        self.menu_scale = wx.MenuItem(self.menu, self.menu_scale_id, '&Scale', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_scale)
        self.menu_scale.Check(True)
        
        self.menu_fullscreen_id = wx.NewId()
        self.menu_fullscreen = wx.MenuItem(self.menu, self.menu_fullscreen_id, '&FullScreen', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_fullscreen)
        self.menu_fullscreen.Check(False)
        
        self.menu_dl_id = wx.NewId()
        self.menu_dl = wx.MenuItem(self.menu, self.menu_dl_id, '&Download From Boards', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_dl)
        self.menu_dl.Check(self.download_enabled)
        
        self.menu_black_id = wx.NewId()
        self.menu_black = wx.MenuItem(self.menu, self.menu_black_id, '&Blacklist This Image')
        self.menu.AppendItem(self.menu_black)
        
        self.menu_gifonly_id = wx.NewId()
        self.menu_gifonly = wx.MenuItem(self.menu, self.menu_gifonly_id, '&Only Download Gifs', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_gifonly)
        self.menu_gifonly.Check(self.gif_only_mode)
        
        self.menu_autoadv_id = wx.NewId()
        self.menu_autoadv = wx.MenuItem(self.menu, self.menu_autoadv_id, '&Auto Advance', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_autoadv)
        self.menu_autoadv.Check(self.image_manager.auto_advance)
        
        self.menu_fapfrenzy_id = wx.NewId()
        self.menu_fapfrenzy = wx.MenuItem(self.menu, self.menu_fapfrenzy_id, '&Fap Frenzy', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_fapfrenzy)
        self.menu_fapfrenzy.Check(self.fap_frenzy)
        
        self.menu_icame_id = wx.NewId()
        self.menu_icame = wx.MenuItem(self.menu, self.menu_icame_id, '&I CAME')
        self.menu.AppendItem(self.menu_icame)
        
        self.menu.AppendSeparator()
        
        self.menu_addfolder_id = wx.NewId()
        self.menu_addfolder = wx.MenuItem(self.menu, self.menu_addfolder_id, '&Add Folder')
        self.menu.AppendItem(self.menu_addfolder)
        
        self.menu_downmng_id = wx.NewId()
        self.menu_downmng = wx.MenuItem(self.menu, self.menu_downmng_id, '&Download Manager')
        self.menu.AppendItem(self.menu_downmng)
        
        self.menu.AppendSeparator()
        
        self.menu_exit_id = wx.NewId()
        self.menu_exit = wx.MenuItem(self.menu, self.menu_exit_id, 'E&xit')
        self.menu.AppendItem(self.menu_exit)
        
        if 0: # menubar is disabled since context menu is easier
            self.menubar = wx.MenuBar()
            self.menubar.Append(self.menu, '&Menu')
            self.SetMenuBar(self.menubar)
        
        # menu bindings
        self.Bind(wx.EVT_MENU, self.OnScale, id=self.menu_scale_id)
        self.Bind(wx.EVT_MENU, self.OnFullScreen, id=self.menu_fullscreen_id)
        self.Bind(wx.EVT_MENU, self.OnDLEnable, id=self.menu_dl_id)
        self.Bind(wx.EVT_MENU, self.OnBlackList, id=self.menu_black_id)
        self.Bind(wx.EVT_MENU, self.OnGifMode, id=self.menu_gifonly_id)
        self.Bind(wx.EVT_MENU, self.OnAutoAdvMode, id=self.menu_autoadv_id)
        self.Bind(wx.EVT_MENU, self.OnFapFrenzy, id=self.menu_fapfrenzy_id)
        self.Bind(wx.EVT_MENU, self.OnICame, id=self.menu_icame_id)
        self.Bind(wx.EVT_MENU, self.OnAddFolder, id=self.menu_addfolder_id)
        self.Bind(wx.EVT_MENU, self.OnDownloadManager, id=self.menu_downmng_id)
        self.Bind(wx.EVT_MENU, self.OnExit, id=self.menu_exit_id)
        
        # mouse bindings
        self.Bind(wx.EVT_LEFT_DOWN,  self.OnLeftDown)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseAny)
        
        # key bindings
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_KEY_UP, self.OnKeyUp)
        
        # visual bindings
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None) # nullify the erase event (framerate)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        
        # show the frame
        self.Show(True)
    
    def OnClose(self, event):
        self.image_manager.save_display_data()
        self.image_manager.save_folder_cfg()
        event.Skip()
    
    def OnScale(self, event):
        self.image_manager.scale_enabled = not self.image_manager.scale_enabled
        self.menu_scale.Check(self.image_manager.scale_enabled)
        self.Unpause()
    
    def OnFullScreen(self, event):
        self.ShowFullScreen(not self.IsFullScreen())
        # let the image manager know the state
        self.image_manager.fullscreen = self.IsFullScreen()
        self.menu_fullscreen.Check(self.image_manager.fullscreen)
        self.Unpause()
    
    def OnDLEnable(self, event):
        self.download_enabled = not self.download_enabled
        self.menu_dl.Check(self.download_enabled)
        self.Unpause()
    
    def OnBlackList(self, event):
        self.image_manager.image_data[self.image_manager.cur_image_path].blacklisted = True
        self.image_manager.switch_image()
        self.Unpause()
    
    def OnGifMode(self, event):
        self.gif_only_mode = not self.gif_only_mode
        self.menu_gifonly.Check(self.gif_only_mode)
        self.Unpause()
    
    def OnAutoAdvMode(self, event):
        self.image_manager.auto_advance = not self.image_manager.auto_advance
        self.menu_autoadv.Check(self.image_manager.auto_advance)
        self.Unpause()
    
    def OnFapFrenzy(self, event):
        self.fap_frenzy = not self.fap_frenzy
        self.image_manager.use_additional_rate = self.fap_frenzy
        if self.fap_frenzy:
            self.image_manager.additional_rate = 0.0
        self.menu_fapfrenzy.Check(self.fap_frenzy)
        self.Unpause()
    
    def OnICame(self, event):
        import wx.lib.dialogs
        msg = ''
        iic = self.image_manager.intensity_image_count
        
        for k, v in iic.items():
            msg += k+':\n'
            msg += '\timages:\t'+str(v[0])+'\n'
            msg += '\tstrokes:\t'+str(v[1])+'\n'
            msg += '\ttime:\t'+str(v[2])+'\n'
            msg += '\n\n'
        
        msg += 'Total:\n'
        msg += '\timages:\t'+str(sum([intense[0] for intense in iic.values()]))+'\n'
        msg += '\tstrokes:\t'+str(sum([intense[1] for intense in iic.values()]))+'\n'
        msg += '\ttime:\t'+str(sum([intense[2] for intense in iic.values()]))
        
        dlg = wx.lib.dialogs.ScrolledMessageDialog(self, msg, "!!!")
        dlg.ShowModal()
        dlg.Destroy()
        self.Unpause()
    
    def OnAddFolder(self, event):
        dlg = wx.DirDialog(self, 'Choose a directory:')
        if dlg.ShowModal() == wx.ID_OK:
            self.image_manager.add_folder_images(dlg.GetPath())
        dlg.Destroy()
        self.Unpause()
    
    def OnDownloadManager(self, event):
        #import wx.lib.scrolledpanel as scrolled
        dlg = DLManagerDialog(self)
        wx.Dialog(self, title='Download Manager', size=(800,600))
        if dlg.ShowModal() == wx.ID_OK:
            pass
        dlg.Destroy()
        self.Unpause()
    
    def OnExit(self, event):
        self.Close()
        exit()
    
    def OnLeftDown(self, event):
        if self.image_manager.paused:
            self.Unpause()
        else:
            self.Pause()
        # we don't want to switch actually
        #else:
        #    for i in self.image_manager.image_data:
        #        switched = self.image_manager.switch_image()
        #        if switched:
        #            break
        event.Skip()

    
    def OnRightDown(self, event):
        self.Pause()
        self.PopupMenu(self.menu)
        event.Skip()
    
    def OnMouseAny(self, event):
        # make the cursor visible and stop the current timer
        if self.mouse_timer is not None:
            self.mouse_timer.Stop()
            self.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))
        
        # set the cursor to vanish in 1 second if there's no movement
        # and we're not paused
        if not self.image_manager.paused:
            def bleh():
                self.SetCursor(wx.StockCursor(wx.CURSOR_BLANK))
                self.mouse_timer = None
            self.mouse_timer = wx.CallLater(1000, bleh)
        
        event.Skip()
    
    def OnKeyDown(self, event):
        if not self.key_state:
            keycode = event.GetKeyCode()

            if keycode == ord('F') or keycode == (wx.WXK_ALT and wx.WXK_RETURN):
                # toggle fullscreen
                self.key_state = True
                self.OnFullScreen(not self.IsFullScreen())
            elif keycode in (wx.WXK_SPACE, wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN):
                self.key_state = True
                # switch to the next image (or previous)
                for i in self.image_manager.image_data:
                    if keycode == wx.WXK_LEFT:
                        switched = self.image_manager.switch_image(self.image_manager.image_history.pop())
                    else:
                        switched = self.image_manager.switch_image()

                    if switched:
                        break
    
    def OnKeyUp(self, event):
        self.key_state = False
    
    def Pause(self):
        self.image_manager.paused = True
    
    def Unpause(self):
        if self.image_manager.paused:
            self.image_manager.paused = False
            self.Refresh()
    
    def OnPaint(self, event):
        if self.download_enabled and len(filter(lambda a: not a.show_count, self.image_manager.image_data.values())) < 40:
            a = self.download_manager.get_new_cached()
            for b in a:
                self.image_manager.add_image_data(b[0], b[1])
        if self.image_manager.paused:
            self.refresh_timer.Restart(100)
        else:
            self.refresh_timer.Restart(30) #16
        self.image_manager.show_image(self)
        


app = wx.App(redirect=False)
mainframe = MainFrame(None, -1, '')
app.MainLoop()
