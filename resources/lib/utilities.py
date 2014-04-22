# -*- coding: utf-8 -*- 

import os
import xbmc, xbmcvfs
import struct
import urllib

def log(module, msg):
    xbmc.log((u"### [%s] - %s" % (module, msg,)).encode('utf-8'), level=xbmc.LOGDEBUG)

def copy_subtitles_on_rar(subtitle_list,lang):
    if not subtitle_list: return False

    file_original_path = urllib.unquote(xbmc.Player().getPlayingFile().decode('utf-8'))  # Full path of a playing file
    if (file_original_path.find("rar://") > -1):
        file_original_path = os.path.dirname(file_original_path[6:])

        # take first subtitles in subtitle_list
        subtitles_path = subtitle_list[0]
        file_original_dir = os.path.dirname(file_original_path)
        file_original_basename = os.path.basename(file_original_path)
        file_original_name, file_original_ext = os.path.splitext(file_original_basename)

        subtitles_basename = os.path.basename(subtitles_path)
        subtitles_name, subtitles_ext = os.path.splitext(subtitles_basename)

        short_lang = xbmc.convertLanguage(lang,xbmc.ISO_639_1)

        final_destination = os.path.join(file_original_dir, file_original_name + "." + short_lang + subtitles_ext)

        result = (xbmcvfs.copy(subtitles_path, final_destination) == 1)
        log(__name__,"[RAR] Copy subtitle: %s result %s" % ([subtitles_path, final_destination], result))
        return result
    else:
        return False

def extract_subtitles(archive_dir):
    xbmc.executebuiltin(('XBMC.Extract("%s")' % archive_dir).encode('utf-8'))
    xbmc.sleep(1000)
    basepath = os.path.dirname(archive_dir)
    extracted_files = os.listdir(basepath)
    exts = [".srt", ".sub", ".txt", ".smi", ".ssa", ".ass" ]
    extracted_subtitles = []
    if len(extracted_files) < 1 :
        return []
    else:
        for extracted_file in extracted_files:
            if os.path.splitext(extracted_file)[1] in exts:
                extracted_subtitles.append(os.path.join(basepath, extracted_file))
    return extracted_subtitles
