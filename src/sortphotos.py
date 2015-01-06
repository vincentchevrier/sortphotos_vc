#!/usr/bin/env python
# encoding: utf-8
"""
sortphotos.py
"""

import os
import sys
import shutil
import fnmatch
import subprocess
import filecmp
from datetime import datetime 
import re

# -------- convenience methods -------------

def purge_string(s):
    allowed = '.0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz'
    return ''.join([x for x in s if x in allowed])

def cmd_exif(tag, fname, command="/opt/bin/exif"):
    return subprocess.check_output([command,'-m','-t',tag,fname]).strip()

def del_dirs(src_dir):
    for dirpath, _, _ in os.walk(src_dir, topdown=False):  # Listing the files
        if dirpath == src_dir:
            break
        try:
            os.rmdir(dirpath)
        except OSError as ex:
            print(ex)
# ---------------------------------------



# --------- main script -----------------

def sortphotos(src_dir, dest_dir, extensions, sort_format, move_files, remove_duplicates,
               ignore_exif, rename=True):


    # some error checking
    if not os.path.exists(src_dir):
        raise Exception('Source directory does not exist')
    if not os.path.exists(dest_dir):
        raise Exception('Destination directory does not exist')


    # find files that have the specified extensions
    matched_files = []

    # check if file system is case sensitive
    case_sensitive_os = True
    if os.path.normcase('A') == os.path.normcase('a'):
        case_sensitive_os = False

    # recurvsively search directory
    for root, dirnames, filenames in os.walk(src_dir):

        # search for all files that match the extension
        for ext in extensions:

            # grab both upper and lower case matches if necessary
            matches = fnmatch.filter(filenames, '*.' + ext.lower())
            if case_sensitive_os:
                matches += fnmatch.filter(filenames, '*.' + ext.upper())

            # add file root and save the matched file in list
            for match in matches:
                matched_files.append(os.path.join(root, match))

    # Linux thumbnails are generated with @ in the filename
    matched_files = [x for x in matched_files if "@" not in x]

    # setup a progress bar
    num_files = len(matched_files)
    idx = 0


    # RE of special cases
    r_wp_mp4 = re.compile('.*WP_([0-9]{8})_[0-9]{3}\.mp4')
    r_gen_vid = re.compile('.*(VID|TRIM)_([0-9]{8}_[0-9]{6})\.(mp4|mkv)')
    r_gen_img = re.compile('.*IMG_([0-9]{8}_[0-9]{6})\.(jpg|JPG)')

    for src_file in matched_files:

        # update progress bar
        numdots = int(20.0*(idx+1)/num_files)
        sys.stdout.write('\r')
        sys.stdout.write('[%-20s] %d of %d ' % ('='*numdots, idx+1, num_files))
        sys.stdout.flush()

        idx += 1
        date_fail = False
	date = None

        # Special cases
        src_basename = os.path.basename(src_file)
        if r_wp_mp4.match(src_basename):
            mo = r_wp_mp4.match(src_basename)
            date = datetime.strptime(mo.groups()[0],'%Y%m%d')
            model = 'WP'
        elif r_gen_vid.match(src_basename):
            mo = r_gen_vid.match(src_basename)
            date = datetime.strptime(mo.groups()[1],'%Y%m%d_%H%M%S')
            model = 'video'
        elif r_gen_img.match(src_basename):
            mo = r_gen_img.match(src_basename)
            date = datetime.strptime(mo.groups()[0],'%Y%m%d_%H%M%S')
            model = 'img'

        # General case
        else:
            # use file time stamp if no valid EXIF dataa
            if ignore_exif:
                date = datetime.fromtimestamp(os.path.getmtime(src_file))
                model = None

            else:
                # look for date in EXIF data
                date_tags = ['Date and Time (original)', 'Date and Time (digitized)', 'Date and Time']
                for tag in date_tags:
                    try:
                        date_str = cmd_exif(tag, src_file)
                        date = datetime.strptime(date_str,"%Y:%m:%d %H:%M:%S")
                        break
                    except:
                        pass

                if date is None:
                    date = datetime.fromtimestamp(os.path.getmtime(src_file))
                    date_fail = True
                    

                # look for model in EXIF data
                try:
                    model = cmd_exif('Model', src_file)
                except:
                    model = None
            
        # create folder structure
        dir_structure = date.strftime(sort_format)
        dirs = dir_structure.split('/')
        dest_file = dest_dir
        for thedir in dirs:
            dest_file = os.path.join(dest_file, thedir)
            if not os.path.exists(dest_file):
                os.makedirs(dest_file)

        # setup destination file
        if rename and not date_fail:
            basename, ext = os.path.splitext(os.path.basename(src_file))
            if model is None:
                model = basename
            model = purge_string(model)
            new_fname = '{}_{}{}'.format(date.strftime('%Y-%m-%d_%H%M%S'), model, ext)
            dest_file = os.path.join(dest_file, new_fname)
        else:
            dest_file = os.path.join(dest_file, os.path.basename(src_file))
        root, ext = os.path.splitext(dest_file)
        #force extension to be lower case
        ext = ext.lower()

        # check for collisions
        append = 1
        fileIsIdentical = False

        while True:

            if os.path.isfile(dest_file):  # check for existing name
                if remove_duplicates and filecmp.cmp(src_file, dest_file):  # check for identical files
                    fileIsIdentical = True
                    break

                else:  # name is same, but file is different
                    dest_file = root + '_' + str(append) + ext
                    append += 1

            else:
                break

        # finally move or copy the file
        if move_files:
            if fileIsIdentical:
                continue  # if file is same, we just ignore it 
            else:
                shutil.move(src_file, dest_file)
        else:
            if fileIsIdentical:
                continue  # if file is same, we just ignore it (for copy option)
            else:
                shutil.copy2(src_file, dest_file)

    print

if __name__ == '__main__':

    import argparse

    # setup command line parsing
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
                                     description='Sort files (primarily photos) into folders by date\nusing EXIF data if possible and file creation date if not')
    parser.add_argument('src_dir', type=str, help='source directory (searched recursively)')
    parser.add_argument('dest_dir', type=str, help='destination directory')
    parser.add_argument('-m', '--move', action='store_true', help='move files instead of copy')
    parser.add_argument('-d', '--delete-dir', action='store_true', help='Remove all empty directories from src_dir')
    parser.add_argument('-s', '--sort', type=str, default='%Y/%m',
                        help="choose destination folder structure using datetime format \n\
https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior. \n\
Use forward slashes / to indicate subdirectory(ies) (independent of your OS convention). \n\
The default is '%%Y/%%m', which separates by year then month (e.g., 2012/11).")
    parser.add_argument('--keep-duplicates', action='store_true',
                        help='If file is a duplicate keep it anyway (after renaming).')
    parser.add_argument('--extensions', type=str, nargs='+',
                        default=['jpg', 'jpeg', 'tiff', 'arw', 'avi', 'mov', 'mp4', 'mts','mkv'],
                        help='file types to sort')
    parser.add_argument('--ignore-exif', action='store_true',
                        help='always use file time stamp even if EXIF data exists')
    parser.add_argument('--keep-filenames',action='store_true',help='Do not rename the files. Default behavior is to rename the files, e.g. 2014-09-04_FinePix_1.jpg')


    # parse command line arguments
    args = parser.parse_args()

    sortphotos(args.src_dir, args.dest_dir, args.extensions, args.sort,
              args.move, not args.keep_duplicates, args.ignore_exif, rename=not args.keep_filenames)


    #If requested, remove all empty directories from source
    if args.delete_dir:
        del_dirs(src_dir)

