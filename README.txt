So I was on 4chan, reading posts, and somebody posted this:

"A script selects and displays an image at random from /h/,
randomly selecting a pressure, speed, and time.
This repeats until the user clicks the "I CAME" button,
after which the user is presented with statistics about the session.

Programmers of /h/, MAKE IT SO."

I thought, "Hey, that sounds cool. Why not?" So I made this thing.


It's open source, written in python, so feel free to poke through it and do whatever you want with it.
fg.exe is simply provided for any windows users who can't be bothered to actually install python.


Running the Program
===================
Windows: Run fg.exe
Linux, Mac OS X, etc: Run fg.py. Make sure you have Python, wxPython, and
beautifulsoup4 installed!


Controls
========
Pause: leftclick
Random image: uparrow / downarrow / spacebar / rightarrow
Go back an image: leftarrow
Fullscreen: f / alt+return
Change pulse colour: r
Quit: q


Image History
=============
fg keeps image history while it's running, in case you really liked a former
image and wish to return to it.
Pressing leftarrow will take you back an image. If there are no more images in
the history stack, leftarrow will do nothing.
Image history is not persistent; it's not saved anywhere.


Selecting Images
================
By default, no boards/threads are selected for the program to download from.

To select threads to download from, go to the Download Manager in the context menu (right-click),
click on the board you want to select from on the left side,
and check "download images from this thread" for any threads you want to download from.
Clicking "ignore this thread" will cause the thread to be pushed
to the bottom of the list the next time the board is loaded.
When Gif Only Mode is enabled, only gifs will be downloaded.
(whatever's in the cache will still be displayed though)

The program creates the /cache/ directory, and saves images there.
If it can't find a connection, or you haven't selected any
boards/threads with the Download Manager, it'll just load stuff from there.

If you want to add files, just drop them in the /cache/ directory, and the program will start off on those.

To add images from a folder without adding them to /cache/,
select Add Folder from the context menu (right-click),
and any images in the folder will be added. (not recursive)


Blacklisting Images
===================
If the program downloads an image you don't like,
just select Blacklist This Image from the context menu (right-click),
and the program won't select the image for viewing in the future.
You can undo this by deleting the "blacklisted:true" line for the image in dispdata.cfg.


Statistics
==========
To see your statistics, select "I CAME" from the conetxt menu (right-click).
Selecting "I CAME" doesn't actually reset the statistics,
so don't worry about clicking it if you haven't actually cum (yet)


Fap Frenzy
==========
When this mode is enabled, the pace will increase a bit after each image is displayed.


Rendering Options
=================
To toggle scaling, select Scale from the context menu. Enabled by default.

To toggle fullscreen, select Fullscreen from the context menu or press F or
Alt+Return.

When an animated image is scaled, it will render best in fullscreen mode.


Posting Options / Download Manager Parsing
==========================================
If the download manager sees that some of the text in the post comment
for an image is in the format "(count)/(speed)/(force)", where:

(count) is a positive number (like: 9, 20, 30)
(speed) is either a text speed (see below) or a decimal number (like 0.1, 2.0, 2.8, 9.9)
(force) is just some text

It will use that data for the image when it's displayed.
Commas, fowardslashes, and backslashes count as separators.

Decimal Number Speeds:
If (speed) is a floating point number, or integer number (a number, possibly with a . part)
the will be the frequency of strokes (eg, how many strokes per second)
so 0.5 would be a stroke every 2 seconds, 1.0 would be 1 stroke a second, 2.5 would be 2.5 strokes a second, etc.

A specific numeric speed can also go on it's own line (surrounded by parentheses),
if you want to use a text speed in the "(count)/(speed)/(force)" line.

Example:
20, fast, light
(2.5)

Text Speeds:
valid text speeds are:
    extremely slow (1 stroke every 4 seconds, 0.25)
    very slow      (1 stroke every 3 seconds, 0.333)
    slow           (1 stroke every 2 seconds, 0.5)
    medium         (1 stroke every second, 1.0)
    normal         (1 stroke every second, 1.0)
    fast           (2 strokes every second, 2.0)
    very fast      (3 strokes every second, 3.0)
    extremely fast (4 strokes every second, 4.0)

Example:
10, extremely slow, force of 1000 suns

Automatic Speeds:
Also if mention "speed" or "pace" in the speed field, and the image is animated, 
the program will attempt to automatically determine the proper speed.
This won't work well if the animation has multiple strokes per playback,
so in the case, it's probably best to include the speed on it's own line. (see above)

Example:
80, same speed as gif, hard


dispdata.cfg
============
display data (count, speed, force) can be directly edited in the "dispdata.cfg" file.
for example, the contents might look like:

file:1243134752865.gif
count:50
speed:1.563
intensity:Anything can go here! Awesome! Even alternative instructions!

file:1268748407427.gif
count:30
speed:0.833


folders.cfg
===========
folders can be added at startup by adding them to the "folder.cfg" file.


spamfilter.cfg
==============
Spam filters can be added here.
Each line should be a regular expression to match against the op post in a thread.
If any text in the op post matches the regular expression,
the thread will not appear in the Download Manager.


Troubleshooting
===============
If fg.exe says you're missing msvcp71.dll, there's a copy in msvcp71.zip.
Extract it into the same directory along with everything else.

If the program just displays the same image over and over, see the 
Selecting Images section.

If you notice that a gif seems to be rendering more slowly than it should,
there's a chance that the delaytime in the gif file is set incorrectly.
This is why I included setgifdelay.py.
Run it, enter the filename, and the delay you want to set for all the frames,
and it will set the delay for every frame to that speed.
Speed is in centiseconds.
A good setting for the delay is about 3.
Don't pick 0, since it's used as the indicator that the file was badly made.
The result will be output in the same folder as the image,
with "setgifdelay_" prepended to the original image's filename.

Notes about browser rendering delay (measured in fractions of a second):
Safari:  less than 0.03 -> 0.03 (makes sense)
Firefox: less than 0.02 -> 0.10 (make some sense)
IE:      less than 0.06 -> 0.10 (make NO sense, 0.9 renders faster than 0.5)
Opera:   less than 0.10 -> 0.10 (consistently slow, probably optimal for phones
or whatever)
Google Chrome is probably the same as Safari, as they both use WebKit for 
rendering


Have you a fun for great good!

- Zephyre & Anonymous
