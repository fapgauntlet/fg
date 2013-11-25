#!/usr/bin/env python

import json
import os
import os.path
import re
import sys
import threading
import time
import urllib2
import wx
import wx.animate
from math import sin, cos, radians
from random import randint, random

# change below to gime.gmtime to bring threads with no bump time to the front (rather than to the back)
BUMPTIME_EMPTY_VAL = time.gmtime(0)

#proxy = {'http':'127.0.0.1:8118'}
proxy = {}

boardlistfallback = [
    'a', 'b', 'c', 'd', 'e', 'f', 'gif', 'h', 'hr', 'k', 'm', 'o', 'p', 'r', 
    's', 't', 'u', 'v', 'vg', 'w', 'wg', 'i', 'ic','r9k','cm', 'y', '3', 'adv',
    'an', 'cgl', 'ck', 'co', 'diy', 'fa', 'fit', 'hc', 'hm', 'int', 'jp', 
    'lit', 'mlp', 'mu', 'n', 'po', 'pol', 'sci', 'soc', 'sp', 'tg', 'toy', 
    'trv', 'tv', 'vp', 'x'
]

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


def getboardlist():
    boardlist = []
    r, _ = openurl('http://api.4chan.org/boards.json')
    if r == None:
        print 'Trouble getting board list; using built-in list'
        boardlist = boardlistfallback
    else:
        for b in r["boards"]:
            boardlist.append(b["board"])
    return boardlist


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


my_path = module_path()
print my_path

cache_dir = os.path.join(my_path, 'cache/')
thumb_cache = os.path.join(cache_dir, 'thumbs/')

if not os.path.exists(cache_dir) or not os.path.isdir(cache_dir):
    os.mkdir(cache_dir)


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
    print 'openurl '+url

    def handle(resp):
        data = None
        if resp.info().getheader("Content-Type") == "application/json":
            data = json.load(resp)
        else:
            data = resp.read()
        lastmod = resp.info().getheader("Last-Modified")
        #resp.close()
        return data, lastmod

    # fix for urllib2 proxy bug
    proxy_support = urllib2.ProxyHandler(proxy)
    opener = urllib2.build_opener(proxy_support)
    
    # create the http request, possibly with a timestamp
    request = urllib2.Request(url)
    if timestamp != None:
        request.add_header('If-Modified-Since', timestamp)
    try:
        resp = opener.open(request)
        # got new data
        return handle(resp)
    except urllib2.HTTPError, errorInfo:
        if errorInfo.code == 404:
            return 404, None
        if errorInfo.code == 304:
            return None, timestamp    # no new data
        return errorInfo.code, None    # some other error


class OpenUrlThreaded(threading.Thread):
    def __init__(self, url, timestamp=None):
        threading.Thread.__init__(self)
        self.url = url
        self.timestamp = timestamp
        self.result = None
    
    def run(self):
        self.result = openurl(self.url, self.timestamp)


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
        self.board = which
        self.npages = 1
        self.page_time = [None]
        self.threads = {}

    def _getcatalog(self):
        return openurl("http://api.4chan.org/%s/catalog.json" % self.board, self.page_time[0])
    
    def _getallthreads(self,catalog):
        threads = []
        for p in catalog:
            threads.extend(p["threads"])
        return threads
        
    def _getthreadbumptime(self, thread):
        if thread.get("last_replies"):
            return thread["last_replies"][-1]["time"]
        else:
            return thread["time"]
    
    def update_iter(self):
        yield self.update()

    def update_page(self, i):
        assert i == 1
        return self.update()
    
    def update(self):
        catalog, _ = self._getcatalog()

        # Last-Modified older than current time, nothing returned
        if not catalog:
            return 0, None

        # same threads, changed threads
        same, changed = 0, 0
        for thread in self._getallthreads(catalog):
            id = thread["no"]
            if id in self.threads:
                old = self.threads[id]
                if old.bump_time != self._getthreadbumptime(thread):
                    old.need_update = True
                    old.bump_time = self._getthreadbumptime(thread)
                    changed += 1
                else:
                    same += 1
            else:
                newthread = ChanThread(self.board, id)
                newthread.need_update = True
                newthread.bump_time = self._getthreadbumptime(thread)
                newthread.addpost(thread)
                changed += 1
                self.threads[id] = newthread

        return changed, same


class ChanThread(object):
    # no week day time hack regex
    noweekday_regex = re.compile(r'\([a-zA-Z]{3,3}?\)')
    
    def __init__(self, board, threadnum):
        self.board = board
        self.threadnum = threadnum
        self.page_time = None
        self.posts = {}
        self.is_source = False
        self.ignore = False
        self.need_update = False
        
    def _getimgurl(self, name, ext):
        return "http://images.4chan.org/%s/src/%s%s" % (self.board, name, ext)
        
    def _getthumburl(self, name):
        return "http://thumbs.4chan.org/%s/thumb/%ss.jpg" % (self.board, name)

    def update(self):
        url = "http://api.4chan.org/%s/res/%s.json" % (self.board, self.threadnum)
        data, self.page_time = openurl(url, self.page_time)
        if data == None:
            return False
            
        added, notadded = 0, 0
        for p in data["posts"]:
            if self.addpost(p):
                added += 1
            else:
                notadded += 1
        return added, notadded
        
    def addpost(self, post):
        id = post["no"]
        if id in self.posts:
            return False
        newpost = {
            "id": id,
            "subject": post.get("sub"),
            "name": post.get("name"),
            "trip": post.get("trip"),
            "time": post["time"],
            "comment": post.get("com", ""),
            "email": post.get("email"),
            "hasimg": False
        }
        if "filename" in post:
            newpost.update({
                "hasimg": True,
                "imgname": post["filename"],
                "imgsize": post["fsize"],
                "imgw": post["w"],
                "imgh": post["h"],
                "imgurl": self._getimgurl(post["tim"], post["ext"]),
                "thumburl": self._getthumburl(post["tim"])
            })
        self.posts[id] = newpost
        return newpost["hasimg"]

    def sorted_posts(self):
        result = self.posts.values()
        result.sort(key=lambda p: p['id'])
        return result
    
    def get_bump_time(self):
        return self.sorted_posts()[-1]["time"]

    def is_gauntlet_thread(self):
        subject = self.sorted_posts()[0]["subject"]
        if not subject:
            return False
        return 'gauntlet' in subject.lower()


class DLManagerDialog(wx.Dialog):
    def __init__(self, parent):
        import wx.lib.scrolledpanel as scrolled
        wx.Dialog.__init__(self, parent, title='Download Manager', size=(800,600), style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)
        self.parent = parent
        
        self.sizer_all = sizer_all = wx.BoxSizer(wx.VERTICAL)
        self.sizer_main = sizer_main = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer_buttons = sizer_buttons = wx.BoxSizer(wx.HORIZONTAL)

        self.boardlist = getboardlist() 
        self.source_box = source_box = wx.ListBox(self, -1, size=(60,-1), choices=self.boardlist)
        self.source_box.SetSelection(0)    # FIXME?
        source_box.Bind(wx.EVT_LISTBOX, self.SourceListBox)
        
        self.thread_panel = thread_panel = scrolled.ScrolledPanel(self)
        self.sizer_thread = wx.BoxSizer(wx.VERTICAL)
        thread_panel.SetSizer(self.sizer_thread)
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
    
    def SourceListBox(self, e):
        label = e.GetString()    
        if not label or not e.IsSelection():
            return
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
        if (label not in self.source_box.GetStrings()) and (label not in self.parent.board_downloaders):
            print '????'
            return
        b = self.parent.board_downloaders[label]
        for n in self.panel_threads: n.Destroy()
        self.panel_threads = []
        self.sizer_thread.Clear()
        self.thread_panel.Show(False)
        cflip = 0
        sorted_threads = b.threads.items()
        sorted_threads.sort(key=lambda i: i[1].get_bump_time())
        sorted_threads.reverse()
        sorted_threads.sort(key=lambda i: not i[1].is_gauntlet_thread()) # show gauntlet threads first
        sorted_threads.sort(key=lambda i: i[1].ignore) # push ignored threads to end of list
        if filter(lambda a: not hasattr(a, 'thumb_bmp'), sorted_threads):
            # figure out which to get
            to_grab = []
            for i, v in enumerate(sorted_threads):
                t_key, thread = v
                op_post = thread.sorted_posts()[0]
                
                if 'thumburl' not in op_post:
                    pass
                elif not hasattr(thread, 'thumb_bmp'):
                    op_thumb_url = op_post['thumburl']
                    to_grab.append((thread, op_thumb_url))
            
            # get the ones we need
            progress = wx.ProgressDialog(
                "Loading Thumbnails",
                'Loading thumbnails for /'+label+'/',
                maximum=len(to_grab),
                parent=self,
                style=wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME
                    | wx.PD_ESTIMATED_TIME | wx.PD_REMAINING_TIME
            )
            needed = len(to_grab)
            max_get = 8
            cur_get = []
            while to_grab or cur_get:
                progress.Update(min(needed-1, needed-len(to_grab)))
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
                            thumb_url = op_post['thumburl']
                            getter = OpenUrlThreaded(thumb_url)
                            getter.start() # begin the thread
                            cur_get.append((thread, getter))
                        
                        # only grab the file if it still exists
                        elif thumb_dat != 404:
                            # write to thumb cache
                            op_post = thread.sorted_posts()[0]
                            thumb_url = op_post['thumburl']
                            thumb_path = os.path.join(thumb_cache, thumb_url.rsplit('/', 1)[-1])
                            try:
                                f = None
                                f = open(thumb_path, 'wb')
                                f.write(thumb_dat)
                            finally:
                                if f != None: f.close()
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

            # create a panel for this thread
            n = wx.Panel(self.thread_panel)
            n.actual_thread_obj = thread
            n_sizer = wx.BoxSizer(wx.VERTICAL)
            # force scroll focusing
            n.force_scrolling = wx.Panel(n, -1, size=(0,0))
            n_sizer.Add(n.force_scrolling)
            class cunt(object):
                def __init__(self, bleh):
                    self.bleh = bleh
                def __call__(self, e):
                    if isinstance(self.bleh.FindFocus(), (wx.TextCtrl, wx.ListBox)):
                        self.bleh.SetFocus()
            n.Bind(wx.EVT_ENTER_WINDOW, cunt(n.force_scrolling))
            
            n_sizer.Add((5,10)) # a little bit of padding

            # content sizer
            content_sizer = wx.BoxSizer(wx.HORIZONTAL)
            content_sizer2 = wx.BoxSizer(wx.VERTICAL)
            
            # thumb display
            #op_thumb_url = op_post['thumburl']
            if hasattr(thread, 'thumb_bmp'):
                bmp = thread.thumb_bmp
                thumb_bmp = wx.StaticBitmap(n, -1, bmp)
                content_sizer.Add(thumb_bmp, 0)
                content_sizer.Add((10,0))
            
            title_sizer = wx.BoxSizer(wx.HORIZONTAL)
            font = wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
            if op_post['subject']:
                # subject
                t = html_to_text(op_post['subject']) #.decode("utf-8", "replace")
                subject = wx.StaticText(n, -1, t)
                subject.SetFont(font)
                subject.SetForegroundColour((204,17,5))
                #content_sizer2.Add(subject)
                title_sizer.Add(subject)
            
            if op_post['name']:
                # poster name
                op_name_text = html_to_text(' '+op_post['name']) #.decode("utf-8", "replace")
                op_name = wx.StaticText(n, -1, op_name_text)
                op_name.SetFont(font)
                op_name.SetForegroundColour((17,119,67))
                title_sizer.Add(op_name)
            '''
            if op_post['trip'] != None:
                op_name_text += ' '+html_to_text(op_post['trip']) #.decode("utf-8", "replace")
            '''
            content_sizer2.Add(title_sizer)
            
            try: # 240, 224, 214 # 255,255,238
                t = html_to_text(op_post['comment']) #.decode("utf-8", "replace")
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
            
            content_sizer.Add(content_sizer2, 1, wx.EXPAND)
            n_sizer.Add(content_sizer, 0, wx.EXPAND)
            
            n_sizer.Add((5,8)) # a little bit of padding

             # download checkbox
            check = wx.CheckBox(n, -1, "Download images from this thread")
            if thread.is_source:
                check.SetValue(True)
            check.Bind(wx.EVT_CHECKBOX, GoddamnButton(check, thread))
            n_sizer.Add(check, 0)
            n.thread_panel_check = check
            
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
    
    def UpdateBoard(self, label):
        # add the board if it doesn't already exist
        if label not in self.parent.board_downloaders:
            self.parent.board_downloaders[label] = ChanBoard(label)
        b = self.parent.board_downloaders[label]
        
        progress = None
        brokeout = False
        
        #'''
        if b.npages == None:
            #cur_pos = 0
            max_requests = 8
            cur_requests = []
            detected_end = None
            for i in xrange(max_requests):
                r_thread = ThreadedResult(b.update_page, i)
                r_thread.start()
                cur_requests.append((i, r_thread))
            while b.npages == None or None in b.page_time:
                if None in b.page_time and len(cur_requests) < max_requests:
                    for i, v in enumerate(b.page_time):
                        if v != None:
                            continue
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
                    if req[1].result != None:
                        cur_requests.remove(req)
                # make a progress dialog if we need one
                if progress == None and b.npages != None:
                    progress = wx.ProgressDialog(
                        "Getting Board Data",
                        'Getting list of threads from /'+label+'/',
                        maximum=b.npages,
                        parent=self,
                        style=wx.PD_CAN_ABORT | 
                            wx.PD_ELAPSED_TIME | 
                            wx.PD_ESTIMATED_TIME | 
                            wx.PD_REMAINING_TIME |
                            wx.PD_AUTO_HIDE
                    )
                # allow breakout from the update
                if progress != None:
                    keepgoing, skip = progress.Update(len(filter(lambda a: a != None, b.page_time)))
                    if not keepgoing:
                        brokeout = True
                        break
                time.sleep(0.1)
        else:
            for i, v in enumerate(b.update_iter()):
                changed_t, same_t = v
                if ((changed_t and not same_t) or not changed_t) and None not in b.page_time:
                    break # everything == current
                if progress == None:
                    progress = wx.ProgressDialog(
                        "Getting Board Data",
                        'Getting list of threads from /'+label+'/',
                        maximum=b.npages,
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
        if progress != None:
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
        self.hist = []
        self.histindex = 0
        self.imgdata = {}
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

        self.pulsecolour = (1.0, 0.0, 1.0)
        
        # test
        for g in self.folders:
            self.add_folder_images(g)
        self.switchimg()
        
    def load_folder_cfg(self, fn=None):
        if fn == None:
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
            if f != None:
                f.close()
    
    def save_folder_cfg(self, fn=None):
        if fn == None:
            fn = 'folders.cfg'
        try:
            f = None
            f = open(fn, 'w')
            n = dict.fromkeys(str(i) for i in self.folders).keys()
            f.write('\n'.join(n))
        except:
            pass
        finally:
            if f != None:
                f.close()
    
    def load_display_data(self, fn=None):
        if fn == None:
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
                if f != None:
                    f.close()
            if f_got != None:
                lines = f_got.splitlines()
                pd = None
                for line in lines:
                    if ':' in line:
                        head, tail = line.split(':', 1)
                        if head == 'file':
                            self.playdata[tail] = pd = {}
                        elif pd != None:
                            if head == 'count' and tail.isdigit():
                                pd['count'] = int(tail)
                            else:
                                pd[head] = tail
    
    def save_display_data(self, fn=None):
        if fn == None:
            fn = 'dispdata.cfg'
        s = ''
        for imgdata in self.imgdata.values():
            bn = imgdata.basename
            if imgdata.count != None:
                if bn not in self.playdata:
                    self.playdata[bn] = {'count':imgdata.count}
                else:
                    self.playdata[bn]['count'] = imgdata.count
            if imgdata.speed != None:
                if bn not in self.playdata:
                    self.playdata[bn] = {'speed':imgdata.speed}
                else:
                    self.playdata[bn]['speed'] = imgdata.speed
            if imgdata.intensity != None:
                if bn not in self.playdata:
                    self.playdata[bn] = {'intensity':imgdata.intensity}
                else:
                    self.playdata[bn]['intensity'] = imgdata.intensity
            if imgdata.blacklisted != None:
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
            if f != None:
                f.close()
    
    def switchimg(self, imagepath=None):
        if self.cur_image_path != None and imagepath == None:
            # put current image in history
            if self.histindex >= len(self.hist):
                self.hist.append(self.cur_image_path)
            else:
                self.hist[self.histindex] = self.cur_image_path
            self.histindex += 1

        if imagepath == None:
            a = self.imgdata.keys()
            if a:
                if 1: # semi-random
                    l = self.imgdata.items()
                    l.sort(key=lambda a: a[1].show_count)
                    l = filter(lambda a: a[1].show_count == l[0][1].show_count, l)
                    imagepath = l[randint(0, len(l)-1)][0]
                    
                    # try to avoid showing the same image twice in a row
                    if imagepath == self.cur_image_path:
                        for i in l:
                            if i != imagepath:
                                switched = self.switchimg(i[0])
                                if switched:
                                    return switched
                else: # ordered
                    a.sort()
                    b = 0
                    if self.cur_image_path != None:
                        if self.cur_image_path in a:
                            b = (a.index(self.cur_image_path) + 1) % len(a)
                    imagepath = a[b]
            else:
                return False
        
        if self.imgdata[imagepath].blacklisted != None:
            self.imgdata[imagepath].show_count += 50
            #del self.imgdata[imagepath]
            return False
        
        # make sure the image exists
        if not os.path.exists(imagepath):
            #if imagepath in self.imgdata:
            #   del self.imgdata[imagepath]
            self.imgdata[imagepath].show_count += 50
            return False
        
        # make sure the image data == stored
        if imagepath not in self.imgdata:
            self.add_imgdata(imagepath)
        
        # load the image
        if imagepath[-4:] == '.gif':
            try:
                ani = wx.animate.Animation(imagepath)
            except:
                self.imgdata[imagepath].show_count += 50
                return False

            # wxPython doesn't support this under Linux, so skip gifs to avoid crash
            if ani.GetFrameCount() == 0:
                self.imgdata[imagepath].show_count += 50
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
                # IE:     (< 0.06) -> 0.10 (make NO sense, 0.7 renders faster than 0.6?)
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
                self.imgdata[imagepath].show_count += 50
                return False
            self.cur_animated = False
            self.cur_ani_index = 0
            self.cur_bitmap = [(n, 0)]
        
        # clear the fullscreen bitmap
        self.fs_bitmap = []
        
        imgdata = self.imgdata[imagepath]
        
        self.cur_image_path = imagepath
        self.cur_image_start_time = time.time()
        
        if imgdata.intensity != None:
            self.cur_intensity = imgdata.intensity
        else:
            intense = intensities[randint(0,len(intensities)-1)]
            self.cur_intensity = intense
        
        if imgdata.speed == None:
            if self.cur_animated:
                if timelen == 0:
                    timelen = 0.1
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
        
        if imgdata.count == None:
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
        self.imgdata[imagepath].show_count += 1
        
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
    
    def showimg(self, parent):
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
                    if self.fs_bitmap[self.cur_ani_index] == None:
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
                tx, ty = 10, dch/2
                dc.DrawText("Paused", tx+1, ty)
                dc.DrawText("Paused", tx-1, ty)
                dc.DrawText("Paused", tx, ty+1)
                dc.DrawText("Paused", tx, ty-1)
                dc.SetTextForeground((255, 255, 255))
                dc.DrawText("Paused", tx, ty)

                # timing stuff
                if self.last_pause_time != None:
                    self.cur_image_start_time += time.time() - self.last_pause_time
                self.last_pause_time = time.time()
                self.last_time = None
            else:
                self.last_pause_time = None
        
                # keep time count for "I came"
                if self.last_time == None:
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
                x = 127.5 - cos(radians(pos*360)) * 127.5
            else:
                x = (pos > 0.5) * 255
            
            # text expands along with colour pulse
            dc.SetFont(wx.Font((1 - 0.2*cos(radians(pos*360))+1) * 16, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            
            self.text = str(max(0, self.cur_count - count)) +', '+ self.cur_intensity
            
            tw, th = dc.GetTextExtent(self.text)
            tx, ty = (dcw-tw)/2, 0
            
            #inv_x = (255-x)/2
            inv_x = 0
            dc.SetTextForeground((inv_x, inv_x, inv_x))
            dc.DrawText(self.text, tx+1, ty)
            dc.DrawText(self.text, tx-1, ty)
            dc.DrawText(self.text, tx, ty+1)
            dc.DrawText(self.text, tx, ty-1)
            c = self.pulsecolour
            dc.SetTextForeground((c[0]*x, c[1]*x, c[2]*x))
            dc.DrawText(self.text, tx, ty)#, dch-th)# 0,0)#
            
            # auto advancement
            if self.auto_advance and count == self.cur_count:
                for i in self.imgdata:
                    switched = self.switchimg()
                    if switched:
                        break

        else:
            dc.SetFont(wx.Font(25, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.SetTextForeground((200, 200, 200))
            dc.DrawText("No images cached yet.", 10, dch/2 - 55)
            dc.DrawText("Right-click to begin.", 10, dch/2 + 5)
            for i in self.imgdata:
                switched = self.switchimg()
                if switched:
                    break
    
    def changepulsecolour(self):
        self.pulsecolour = (random(), random(), random())

    def add_imgdata(self, path, extra_data=None):
        if path not in self.imgdata:
            self.imgdata[path] = ImageData(path)
        imgdat = self.imgdata[path]
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
        elif extra_data != None:
            imgdat.count, imgdat.speed, imgdat.intensity = extra_data
    
    def add_folder_images(self, path):
        if os.path.isdir(path):
            for n in os.listdir(path):
                m = os.path.join(path, n)
                if os.path.isfile(m):
                    if os.path.splitext(m)[1] in ('.gif', '.jpg', '.bmp', '.png'):
                        self.add_imgdata(m)
    
    def rem_folder_images(self, path):
        if os.path.isdir(path):
            if path[-1] in ('\\', '/'):
                path = os.path.dirname(path)
            for i in self.imgdata.keys():
                if os.path.dirname(i) == path:
                    del self.imgdata[i]


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
            sleep = 0.01
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
                        image_posts.extend(filter(lambda p: 'imgurl' in p, t.posts.values()))
                    to_get = []
                    pd = self.parent.imgmanager.playdata
                    for img_post in image_posts:
                        image_base = img_post['imgurl'].rsplit('/', 1)[-1]
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
                        if meh != None:
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
                                if speed_index != None:
                                    break
                            
                            # find the speed (if auto-pacing didn't find it)
                            for i, v in enumerate(parts):
                                # if we already have a speed, we don't have to look further
                                if speed_index != None:
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
                                if num != None:
                                    detected_speed = float(num.group(1))
                                    speed_index = i
                                    continue # got a float speed
                            
                            # if we got a speed, find the force
                            if speed_index != None:
                                # if the speed == at the begining, use everything after it for the force
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
                                if num != None:
                                    detected_speed = float(num.group(1))
                                    break
                            
                            # even if we don't have a force or speed, we at least have a count
                            extra_data = detected_count, detected_speed, detected_force
                        imgurl = which['imgurl']
                        print "Downloading " + imgurl + " ...",
                        got, mod_time = openurl(imgurl)
                        image_base = imgurl.rsplit('/', 1)[-1]
                        img_cache_path = cache_dir + image_base
                        if got != 404 and got != None:
                            f = open(img_cache_path, 'wb')
                            f.write(got)
                            f.close()
                            self.new_cached.append((img_cache_path, extra_data))
                            print "done"
                    else:
                        need_refresh = True
                        sleep = 0.5
                last_refresh = time.time() - self.last_full_refresh
                if not need_refresh and (last_refresh > self.max_refresh_delay):
                    sleep = 0.0
                    for b in self.parent.board_downloaders.values():
                        b.update()
                    self.last_full_refresh = time.time()
                if need_refresh and (last_refresh > self.min_refresh_delay):
                    sleep = 0.0
                    for b in self.parent.board_downloaders.values():
                        b.update()
                    self.last_full_refresh = time.time()

            except wx.PyDeadObjectError:
                sys.exit()
            except:
                import traceback
                print 'Error in download management thread, attempting to recover'
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
        self.panel = MainPanel(self, wx.ID_ANY)
        self.panel.SetFocus()
        self.Show(True)

class MainPanel(wx.Panel):
    def refresh_window(self, event):
        self.Refresh()

    def __init__(self, parent, id):
        wx.Panel.__init__(self, parent, id, size=(800,600))
        self.board_downloaders = {}
        self.download_enabled = True
        self.gif_only_mode = False
        self.mouse_timer = None
        self.key_state = False
        self.fap_frenzy = False
        
        self.imgmanager = ImageManager()
        self.download_manager = DownloadManager(self)
        self.download_manager.start()

        self.refresh_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.refresh_window, self.refresh_timer)
        self.refresh_timer.Start(100)
        
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
        self.menu_fullscreen = wx.MenuItem(self.menu, self.menu_fullscreen_id, '&Fullscreen', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_fullscreen)
        self.menu_fullscreen.Check(False)
        
        self.menu_dl_id = wx.NewId()
        self.menu_dl = wx.MenuItem(self.menu, self.menu_dl_id, '&Download from boards', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_dl)
        self.menu_dl.Check(self.download_enabled)
        
        self.menu_black_id = wx.NewId()
        self.menu_black = wx.MenuItem(self.menu, self.menu_black_id, '&Blacklist this image')
        self.menu.AppendItem(self.menu_black)
        
        self.menu_gifonly_id = wx.NewId()
        self.menu_gifonly = wx.MenuItem(self.menu, self.menu_gifonly_id, '&Only download gifs', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_gifonly)
        self.menu_gifonly.Check(self.gif_only_mode)
        
        self.menu_autoadv_id = wx.NewId()
        self.menu_autoadv = wx.MenuItem(self.menu, self.menu_autoadv_id, '&Auto advance', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_autoadv)
        self.menu_autoadv.Check(self.imgmanager.auto_advance)
        
        self.menu_fapfrenzy_id = wx.NewId()
        self.menu_fapfrenzy = wx.MenuItem(self.menu, self.menu_fapfrenzy_id, '&Fap Frenzy', kind=wx.ITEM_CHECK)
        self.menu.AppendItem(self.menu_fapfrenzy)
        self.menu_fapfrenzy.Check(self.fap_frenzy)
        
        self.menu_icame_id = wx.NewId()
        self.menu_icame = wx.MenuItem(self.menu, self.menu_icame_id, '&I CAME')
        self.menu.AppendItem(self.menu_icame)
        
        self.menu.AppendSeparator()
        
        self.menu_addfolder_id = wx.NewId()
        self.menu_addfolder = wx.MenuItem(self.menu, self.menu_addfolder_id, '&Add folder')
        self.menu.AppendItem(self.menu_addfolder)
        
        self.menu_downmng_id = wx.NewId()
        self.menu_downmng = wx.MenuItem(self.menu, self.menu_downmng_id, '&Download manager')
        self.menu.AppendItem(self.menu_downmng)
        
        self.menu.AppendSeparator()
        
        self.menu_exit_id = wx.NewId()
        self.menu_exit = wx.MenuItem(self.menu, self.menu_exit_id, '&Exit')
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
        self.imgmanager.save_display_data()
        self.imgmanager.save_folder_cfg()
        event.Skip()
    
    def OnScale(self, event):
        self.imgmanager.scale_enabled = not self.imgmanager.scale_enabled
        self.menu_scale.Check(self.imgmanager.scale_enabled)
        self.Unpause()
    
    def OnFullScreen(self, event):
        self.ShowFullScreen(not self.IsFullScreen())
        # let the image manager know the state
        self.imgmanager.fullscreen = self.IsFullScreen()
        self.menu_fullscreen.Check(self.imgmanager.fullscreen)
        self.Unpause()
    
    def OnDLEnable(self, event):
        self.download_enabled = not self.download_enabled
        self.menu_dl.Check(self.download_enabled)
        self.Unpause()
    
    def OnBlackList(self, event):
        self.imgmanager.imgdata[self.imgmanager.cur_image_path].blacklisted = True
        self.imgmanager.switchimg()
        self.Unpause()
    
    def OnGifMode(self, event):
        self.gif_only_mode = not self.gif_only_mode
        self.menu_gifonly.Check(self.gif_only_mode)
        self.Unpause()
    
    def OnAutoAdvMode(self, event):
        self.imgmanager.auto_advance = not self.imgmanager.auto_advance
        self.menu_autoadv.Check(self.imgmanager.auto_advance)
        self.Unpause()
    
    def OnFapFrenzy(self, event):
        self.fap_frenzy = not self.fap_frenzy
        self.imgmanager.use_additional_rate = self.fap_frenzy
        if self.fap_frenzy:
            self.imgmanager.additional_rate = 0.0
        self.menu_fapfrenzy.Check(self.fap_frenzy)
        self.Unpause()
    
    def OnICame(self, event):
        import wx.lib.dialogs
        msg = ''
        iic = self.imgmanager.intensity_image_count
        
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
            self.imgmanager.add_folder_images(dlg.GetPath())
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
        if self.imgmanager.paused:
            self.Unpause()
        else:
            self.Pause()
        # we don't want to switch actually
        #else:
        #   for i in self.imgmanager.imgdata:
        #       switched = self.imgmanager.switchimg()
        #       if switched:
        #           break
        event.Skip()

    
    def OnRightDown(self, event):
        self.Pause()
        self.PopupMenu(self.menu)
        event.Skip()
    
    def OnMouseAny(self, event):
        # make the cursor visible and stop the current timer
        if self.mouse_timer != None:
            self.mouse_timer.Stop()
            self.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))
        
        # set the cursor to vanish in 1 second if there's no movement
        # and we're not paused
        if not self.imgmanager.paused:
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
            elif keycode == ord('R'):
                self.imgmanager.changepulsecolour()
            elif keycode in (wx.WXK_SPACE, wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN):
                switched = None
                self.key_state = True
                # switch to the next image (or previous)
                for i in self.imgmanager.imgdata:
                    if keycode == wx.WXK_LEFT:
                        img = None
                        if self.imgmanager.histindex > 0:
                            self.imgmanager.histindex -=  1
                            prev = self.imgmanager.hist[self.imgmanager.histindex]
                            switched = self.imgmanager.switchimg(prev)
                    else:
                        switched = self.imgmanager.switchimg()

                    if switched:
                        break
            elif keycode == ord('Q'):
                self.Close()
                sys.exit()  
    
    def OnKeyUp(self, event):
        self.key_state = False
    
    def Pause(self):
        self.imgmanager.paused = True
    
    def Unpause(self):
        if self.imgmanager.paused:
            self.imgmanager.paused = False
            self.Refresh()
    
    def OnPaint(self, event):
        if self.download_enabled and len(filter(lambda a: not a.show_count, self.imgmanager.imgdata.values())) < 40:
            a = self.download_manager.get_new_cached()
            for b in a:
                self.imgmanager.add_imgdata(b[0], b[1])
        if self.imgmanager.paused:
            self.refresh_timer.Start(100)
        else:
            self.refresh_timer.Start(30) #16
        self.imgmanager.showimg(self)

app = wx.App(redirect=False)
mainframe = MainFrame(None, -1, 'Gauntlet')
app.MainLoop()

