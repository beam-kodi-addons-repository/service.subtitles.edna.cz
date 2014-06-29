# # -*- coding: utf-8 -*- 

from utilities import log
import urllib, re, os, copy, xbmc, xbmcgui
import HTMLParser
from stats import results_with_stats

class EdnaClient(object):

	def __init__(self,addon):
		self.server_url = "http://www.edna.cz"
		self.addon = addon
		self._t = addon.getLocalizedString

	def download(self,link):

		dest_dir = os.path.join(xbmc.translatePath(self.addon.getAddonInfo('profile').decode("utf-8")), 'temp')
		dest = os.path.join(dest_dir, "download.tmp")

		log(__name__,'Downloading subtitles from %s' % link)
		res = urllib.urlopen(link)
		
		subtitles_filename = re.search("Content\-Disposition: attachment; filename=\"(.+?)\"",str(res.info())).group(1)
		log(__name__,'Filename: %s' % subtitles_filename)
		subtitles_format = re.search("\.(\w+?)$", subtitles_filename, re.IGNORECASE).group(1)
		log(__name__,"Subs in %s" % subtitles_format)
		
		subtitles_data = res.read()

		log(__name__,'Saving to file %s' % dest)
		zip_file = open(dest,'wb')
		zip_file.write(subtitles_data)
		zip_file.close()

		final_dest = os.path.join(dest_dir, "download." + subtitles_format)

		log(__name__,'Changing filename to %s' % final_dest)
		os.rename(dest, final_dest)

		return final_dest

	def normalize_input_title(self, title):
		if self.addon.getSetting("search_title_in_brackets") == "true":
			log(__name__, "Searching title in brackets - %s" % title)
			search_second_title = re.match(r'.+ \((.{3,})\)',title)
			if search_second_title and not re.search(r'^[\d]{4}$',search_second_title.group(1)): title = search_second_title.group(1)
		
		if re.search(r', The$',title,re.IGNORECASE):
			log(__name__, "Swap The - %s" % title)
			title =  "The " + re.sub(r'(?i), The$',"", title) # normalize The
		
		if self.addon.getSetting("try_cleanup_title") == "true":
			log(__name__, "Title cleanup - %s" % title)
			title = re.sub(r"(\[|\().+?(\]|\))","",title) # remove [xy] and (xy)

		return title.strip()

	def search(self, item):

		if item['mansearch']:
			title = item['mansearchstr']
			dialog = xbmcgui.Dialog()
			item['season'] = dialog.numeric(0, self._t(32111), item['season'])
			item['episode'] = dialog.numeric(0, self._t(32111), item['episode'])
		else:
			title = self.normalize_input_title(item['tvshow'])

		if not title or not item['season'] or not item['episode']:
			xbmc.executebuiltin("XBMC.Notification(%s,%s,5000,%s)" % (
						self.addon.getAddonInfo('name'), self._t(32110),
						os.path.join(xbmc.translatePath(self.addon.getAddonInfo('path')).decode("utf-8"),'icon.png')
			))
			log(__name__, ["Input validation error", title, item['season'], item['episode']])
			return results_with_stats(None, self.addon, title, item)

		tvshow_url = self.search_show_url(title)
		if tvshow_url == None: return results_with_stats(None, self.addon, title, item)

		found_season_subtitles = self.search_season_subtitles(tvshow_url,item['season'])
		log(__name__, ["Season filter", found_season_subtitles])

		episode_subtitle_list = self.filter_episode_from_season_subtitles(found_season_subtitles,item['season'],item['episode'])
		log(__name__, ["Episode filter", episode_subtitle_list])
		if episode_subtitle_list == None: return results_with_stats(None, self.addon, title, item)

		lang_filetred_episode_subtitle_list = self.filter_subtitles_by_language(item['3let_language'], episode_subtitle_list)
		log(__name__, ["Language filter", lang_filetred_episode_subtitle_list])
		if lang_filetred_episode_subtitle_list == None: return results_with_stats(None, self.addon, title, item)

		result_subtitles = []
		for episode_subtitle in lang_filetred_episode_subtitle_list['versions']:

			result_subtitles.append({
				'filename': HTMLParser.HTMLParser().unescape(lang_filetred_episode_subtitle_list['full_title']),
				'link': self.server_url + episode_subtitle['link'],
				'lang': episode_subtitle['lang'],
				'rating': "0",
				'sync': False,
				'lang_flag': xbmc.convertLanguage(episode_subtitle['lang'],xbmc.ISO_639_1),
			})

		log(__name__,["Search result", result_subtitles])

		return results_with_stats(result_subtitles, self.addon, title, item)

	def filter_subtitles_by_language(self, set_languages, subtitles_list):
		if not set_languages: return subtitles_list

		log(__name__, ['Filter by languages', set_languages])
		filter_subtitles_list = []
		for subtitle in subtitles_list['versions']:
			if xbmc.convertLanguage(subtitle['lang'],xbmc.ISO_639_2) in set_languages:
				filter_subtitles_list.append(subtitle)

		if not filter_subtitles_list:
			if "cze" not in set_languages and "slo" not in set_languages:
				dialog = xbmcgui.Dialog()
				if dialog.yesno(self.addon.getAddonInfo('name'), self._t(32100), self._t(32101)):
					xbmc.executebuiltin("ActivateWindow(videossettings)")
			return None
		else:
			filter_results_list = copy.deepcopy(subtitles_list)
			filter_results_list['versions'] = filter_subtitles_list
			return filter_results_list

	def filter_episode_from_season_subtitles(self, season_subtitles, season, episode):
		for season_subtitle in season_subtitles:
			if (season_subtitle['episode'] == int(episode) and season_subtitle['season'] == int(season)):
				return season_subtitle
		return None

	def search_show_url(self,title):
		log(__name__,"Starting search by TV Show: %s" % title)
		if not title: return None

		enc_title = urllib.urlencode({ "q" : title})
		res = urllib.urlopen(self.server_url + "/vyhledavani/?" + enc_title)
		found_tv_shows = []
		if re.search("/vyhledavani/\?q=",res.geturl()):
			log(__name__,"Parsing search result")
			res_body = re.search("<ul class=\"list serieslist\">(.+?)</ul>",res.read(),re.IGNORECASE | re.DOTALL)
			if res_body:
				for row in re.findall("<li>(.+?)</li>", res_body.group(1), re.IGNORECASE | re.DOTALL):
					show = {}
					show_reg_exp = re.compile("<h3><a href=\"(.+?)\">(.+?)</a></h3>",re.IGNORECASE | re.DOTALL)
					show['url'], show['title'] = re.search(show_reg_exp, row).groups()
					found_tv_shows.append(show)
		else:
			log(__name__,"Parsing redirect to show URL")
			show = {}
			show['url'] = re.search(self.server_url + "(.+)",res.geturl()).group(1)
			show['title'] = title
			found_tv_shows.append(show)
		
		if (len(found_tv_shows) == 0):
			log(__name__,"No TV Show found")
			return None
		elif (len(found_tv_shows) == 1):
			log(__name__,"One TV Show found, autoselecting")
			tvshow_url = found_tv_shows[0]['url']
		else:
			log(__name__,"More TV Shows found, user dialog for select")
			menu_dialog = []
			for found_tv_show in found_tv_shows: menu_dialog.append(found_tv_show['title'])
			dialog = xbmcgui.Dialog()
			found_tv_show_id = dialog.select(self._t(32003), menu_dialog)
			if (found_tv_show_id == -1): return None # cancel dialog
			tvshow_url = found_tv_shows[found_tv_show_id]['url']
		
		log(__name__,"Selected show URL: " + tvshow_url)
		return tvshow_url

	def search_season_subtitles(self, show_url, show_series):
		res = urllib.urlopen(self.server_url + show_url + "titulky/?season=" + show_series)
		if not res.getcode() == 200: return []
		subtitles = []
		html_subtitle_table = re.search("<table class=\"episodes\">.+<tbody>(.+?)</tbody>.+</table>",res.read(), re.IGNORECASE | re.DOTALL)
		if html_subtitle_table == None: return []
		for html_episode in re.findall("<tr>(.+?)</tr>", html_subtitle_table.group(1), re.IGNORECASE | re.DOTALL):
			subtitle = {}
			show_title_with_numbers = re.sub("<[^<]+?>", "",re.search("<h3>(.+?)</h3>", html_episode).group(1))
			subtitle['full_title'] = show_title_with_numbers
			show_title_with_numbers = re.search("S([0-9]+)E([0-9]+): (.+)",show_title_with_numbers).groups()
			subtitle['season'] = int(show_title_with_numbers[0])
			subtitle['episode'] = int(show_title_with_numbers[1])
			subtitle['title'] = show_title_with_numbers[2]
			subtitle['versions'] = []
			for subs_url, subs_lang in re.findall("a href=\"(.+?)\" class=\"flag\".+?><i class=\"flag\-.+?\">(cz|sk)</i>",html_episode):
				subtitle_version = {}
				# hack na slovenske titulky titulky/?subslang=sk#content
				subtitle_version['link'] = re.sub("direct=1\?","direct=1&",re.sub(r"/titulky/(.*)#content",r"/titulky/?direct=1\1",subs_url))
				subtitle_version['lang'] = subs_lang.upper()
				if subtitle_version['lang'] == "CZ": subtitle_version['lang'] = "Czech" 
				if subtitle_version['lang'] == "SK": subtitle_version['lang'] = "Slovak"
					
				subtitle['versions'].append(subtitle_version)
			if len(subtitle['versions']) > 0: subtitles.append(subtitle)
		return subtitles


