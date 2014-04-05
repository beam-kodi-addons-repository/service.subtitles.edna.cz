# # -*- coding: utf-8 -*- 

from utilities import log, file_size_and_hash
import urllib, re, os, xbmc, xbmcgui
import HTMLParser

class EdnaClient(object):

	def __init__(self,addon):
		self.server_url = "http://www.edna.cz"
		self.addon = addon

	def download(self,link):

		dest_dir = os.path.join(xbmc.translatePath(self.addon.getAddonInfo('profile').decode("utf-8")), 'temp')
		dest = os.path.join(dest_dir, "download.zip")

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

	def search(self, item):
		tvshow_url = self.search_show_url(item['tvshow'])
		if tvshow_url == None:
			return None

		file_size, file_hash = file_size_and_hash(item['file_original_path'], item['rar'])
		log(__name__, "File size: " + str(file_size))

		found_season_subtitles = self.search_season_subtitles(tvshow_url,item['season'])
		episode_subtitle_list = self.filter_episode_from_season_subtitles(found_season_subtitles,item['season'],item['episode'])
		if episode_subtitle_list == None:
			return None

		result_subtitles = []
		for episode_subtitle in episode_subtitle_list['versions']:

			result_subtitles.append({
				'filename': HTMLParser.HTMLParser().unescape(episode_subtitle_list['full_title']),
				'link': self.server_url + episode_subtitle['link'],
				'lang': episode_subtitle['lang'],
				'rating': "0",
				'sync': False,
				'lang_flag': xbmc.convertLanguage(episode_subtitle['lang'],xbmc.ISO_639_1),
			})

		log(__name__,"Search RESULT")
		log(__name__,result_subtitles)
		return result_subtitles

	def filter_episode_from_season_subtitles(self, season_subtitles, season, episode):
		episode_subtitle_list = None

		for season_subtitle in season_subtitles:
			if (season_subtitle['episode'] == int(episode) and season_subtitle['season'] == int(season)):
				episode_subtitle_list = season_subtitle
				break

		log(__name__, episode_subtitle_list)
		return episode_subtitle_list

	def search_show_url(self,title):
		log(__name__,"Starting search by TV Show")
		if (title == None or title == ''):
			log(__name__,"No TVShow name, stop")
			return None

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
		
		if (found_tv_shows.__len__() == 0):
			log(__name__,"TVShow not found, stop")
			return None
		elif (found_tv_shows.__len__() == 1):
			log(__name__,"One TVShow found, auto select")
			tvshow_url = found_tv_shows[0]['url']
		else:
			log(__name__,"More TVShows found, user dialog for select")
			menu_dialog = []
			for found_tv_show in found_tv_shows:
				menu_dialog.append(found_tv_show['title'])
			dialog = xbmcgui.Dialog()
			# TODO: translate
			found_tv_show_id = dialog.select("Select TV show", menu_dialog)
			if (found_tv_show_id == -1):
				return None
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
				subtitle_version['link'] = re.sub("/titulky/#content","/titulky/?direct=1",subs_url)
				subtitle_version['lang'] = subs_lang.upper()
				if subtitle_version['lang'] == "CZ": subtitle_version['lang'] = "Czech" 
				if subtitle_version['lang'] == "SK": subtitle_version['lang'] = "Slovak"
					
				subtitle['versions'].append(subtitle_version)
			if subtitle['versions'].__len__() > 0: subtitles.append(subtitle)
		return subtitles


