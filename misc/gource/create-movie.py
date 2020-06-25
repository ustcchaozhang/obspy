#!/usr/bin/env python

# Produce a video depicting git activity between releases. Unfortunately,
# there is reliably split between the master and releases branches, so for
# 0.9.0, we start at an arbitrary point corresponding to 0.9.0rc1.

from __future__ import (absolute_import, division, print_function)

import hashlib
import os
import subprocess

import requests


TITLE = 'ObsPy 0.10.1 Development'
START = '2013-12-09 14:24:51 +01'
END = '2015-03-20 12:59:18 +01'

WIDTH = 1920
HEIGHT = 1080
FPS = 30

AVATAR_SIZE = 90
AVATAR_DIR = 'avatar'

FONT_FILE = '/usr/share/fonts/bitstream-vera/Vera.ttf'
MUSIC = 'Severe Tire Damage.mp3'
MUSIC_COPYRIGHT = (
    '''Music: "Severe Tire Damage" Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 3.0
https://creativecommons.org/licenses/by/3.0/''')


def fetch_avatar():
    if not os.path.exists(AVATAR_DIR):
        os.mkdir(AVATAR_DIR)

    try:
        log = subprocess.check_output(['git', 'log',
                                       '--pretty=format:%ae!%an'])
    except OSError, subprocess.CalledProcessError:
        print('ERROR: Unable to read git log.')
        exit(1)

    authors = [entry.split('!', 1)
               for entry in log.decode('utf-8').splitlines()]
    unique_authors = set()

    for email, author in authors:
        author = author.strip()
        if author in unique_authors:
            continue
        unique_authors.add(author)

        filename = os.path.join(AVATAR_DIR, author + '.png')
        if os.path.exists(filename):
            continue

        m = hashlib.md5()
        m.update(email.strip().lower().encode())
        uri = 'https://www.gravatar.com/avatar/%s?d=404&size=%d' % (
            m.hexdigest(),
            AVATAR_SIZE)

        print('fetching image for "%s" %s (%s)...' % (author, email, uri))

        resp = requests.get(uri, stream=True)
        if resp.status_code == 200:
            with open(filename, 'wb') as fh:
                for data in resp.iter_content():
                    fh.write(data)


def read_ppm_header(fh):
    try:
        # P6 - magic number
        data = fh.readline()
        assert data == b'P6\n'
        # Gource comment
        data = fh.readline()
        assert data == b'# Generated by Gource\n'
        # Width/height
        data = fh.readline()
        assert data == b'%d %d\n' % (WIDTH, HEIGHT)
        # Max val
        data = fh.readline()
        assert data == '255\n'
    except AssertionError:
        return False
    else:
        return True


# DRY
fps_str = '%f' % (FPS, )
logo = os.path.join(os.pardir, 'docs', 'source', '_static', 'obspy_logo.png')

# Prepare avatar images
fetch_avatar()

# Time and speed are geared for ~1 year of development. Based on
# https://developer.atlassian.com/blog/2015/02/a-year-in-bitbucket-seen-through-gource/
gource_command = ['gource', '-%dx%d' % (WIDTH, HEIGHT),
                  '--start-date', START, '--stop-date', END,
                  '--multi-sampling',
                  '-s', '0.1', '--auto-skip-seconds', '0.25',
                  '--max-file-lag', '0.2',
                  '--max-user-speed', '150', '--user-friction', '1',
                  '--user-image-dir', 'avatar', '--user-scale', '2',
                  '--hide', 'progress,filenames,usernames,mouse',
                  '-r', fps_str,
                  '--title', TITLE,
                  '--logo', logo,
                  '--bloom-multiplier', '1.1', '--bloom-intensity', '0.4',
                  '-o', 'obspy-devel.ppm']
xvfb_command = ['xvfb-run', '-a', '-s', '-screen 0 %dx%dx24' % (WIDTH, HEIGHT)]
subprocess.call(['echo'] + xvfb_command + gource_command)
subprocess.call(xvfb_command + gource_command)

# Calculate number of frames in file
frames = 0
with open('obspy-devel.ppm', 'rb') as fh:
    while read_ppm_header(fh):
        frames += 1
        fh.seek(WIDTH * HEIGHT * 3, 1)
print(frames)
posttime = frames / FPS + 2

# Main video
input0 = ['-f', 'image2pipe', '-r', fps_str, '-vcodec', 'ppm',
          '-i', 'obspy-devel.ppm']
# Logo
input1 = ['-loop', '1', '-framerate', fps_str, '-i', logo]
# Music
input2 = ['-i', MUSIC]

# Additional simple inputs
null_input = 'nullsrc=r=%f:s=%dx%d:d=%f, setpts=PTS-STARTPTS [null];' % (
    FPS,
    WIDTH,
    HEIGHT,
    posttime)
blank_input = 'color=c=0x1a1a1a:r=%f:s=%dx%s [blank];' % (FPS, WIDTH, HEIGHT)

# Create logo fade-in at beginning
logo_fade = '[1:v] trim=duration=4.25, fade=t=in:st=0.25:d=2:alpha=1 [logo];'
pre_video = '''
[blank][logo]
overlay=
    x='if(lte(t, 2.25),
          (main_w - overlay_w) / 2,
          if(lte(t, 4.25),
             (main_w - overlay_w) / 2 -
              ((main_w - overlay_w) / 4 - 10) * (cos(PI * (t - 2.25) / 2) - 1),
             main_w - overlay_w - 10))':
    y='if(lte(t, 2.25),
          (main_h - overlay_h) / 2,
          if(lte(t, 4.25),
             (main_h - overlay_h) / 2 -
              ((main_h - overlay_h) / 4 - 10) * (cos(PI * (t - 2.25) / 2) - 1),
             main_h - overlay_h - 10))':
    shortest=1,
format=yuv420p,
setpts=PTS-STARTPTS [pre];'''.replace('\n', '').replace(' ', '')

# Make main video a little longer
fix_main_pts = '[0:v] setpts=PTS-STARTPTS [main];'
main_extension = ('[null][main] overlay, format=yuv420p, setpts=PTS-STARTPTS '
                  '[mainpost];')

# Add credits to extended main video
post_video = '''
[mainpost]
drawtext=
    fontfile={fontfile}:
    text='Created with gource':
    fontcolor=white:
    enable='between(t,{starttime},{endtime})':
    x=w - text_w - 2 * max_glyph_w:
    y=(h - text_h) / 2 - line_h:
    fontsize=40,
drawtext=
    fontfile={fontfile}:
    text='http\\://acaudwell.github.io/Gource/':
    fontcolor=white:
    enable='between(t,{starttime},{endtime})':
    x=w - text_w - 4 * max_glyph_w:
    y=(h - text_h) / 2 + line_h:
    fontsize=20,
drawtext=
    fontfile={fontfile}:
    text='{copyright}':
    fontcolor=white:
    enable='between(t,{starttime},{endtime})':
    x=w - text_w - 4 * max_glyph_w:
    y=h / 2 + 2.5 * line_h:
    fontsize=20,
setpts=PTS-STARTPTS [mainpostfont];'''.replace('\n', '')
copyright = MUSIC_COPYRIGHT.replace('\\', '\\\\').replace(':', '\\:')
post_video = post_video.format(fontfile=FONT_FILE, copyright=copyright,
                               starttime=frames / FPS, endtime=posttime)

# Combine all videos
video_concat = '[pre][mainpostfont] concat=n=2:v=1:a=0 [video_out];'

# Fade out audio at end of everything
audio_fade = '[2:a] atrim=duration=%f, afade=t=out:st=%f:d=1 [audio_out]' % (
    frames / FPS + 4.25 + 2,
    frames / FPS + 4.25 + 1)

filter_command = ['-filter_complex',
                  null_input + blank_input +
                  logo_fade + pre_video +
                  fix_main_pts + main_extension + post_video +
                  video_concat +
                  audio_fade]

ffmpeg_command = (['ffmpeg', '-y'] +
                  input0 + input1 + input2 + filter_command +
                  ['-map', '[video_out]',
                   '-vcodec', 'libvpx',
                   '-b:v', '25000k',
                   '-map', '[audio_out]',
                   '-acodec', 'libvorbis',
                   '-b:a', '256k',
                   '-aq', '4',
                   '-shortest',
                   'obspy-devel.webm'])
subprocess.call(['echo'] + ffmpeg_command)
subprocess.call(ffmpeg_command)
