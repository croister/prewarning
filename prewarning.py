from _hashlib import new

__author__ = 'croister'

from tkinter import Tk, Frame, Label, X, Y, BOTH, TOP, BOTTOM, LEFT, RIGHT, CENTER, NSEW, N, S, E, W, Event
from tkinter.ttk import Treeview, Style
from time import strftime, sleep
from datetime import datetime, timedelta
from queue import Queue
from threading import Thread
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError
from zipfile import ZipFile
from xml.etree import ElementTree
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
from subprocess import call
from configparser import ConfigParser
from os import stat, path
import socket


# class App(Frame, FileSystemEventHandler):
class App(Frame):

	def __init__(self, parent):

		# screen_width = 768
		screen_width = parent.winfo_screenwidth()
		print('Screen width: ' + str(screen_width))
		# screen_height = 1366
		screen_height = parent.winfo_screenheight()
		print('Screen height: ' + str(screen_height))
		# font_factor = 28
		font_factor = 27
		if screen_width <= screen_height:
			# font_factor = 15
			font_factor = 16
		print('Font factor: ' + str(font_factor))

		self.default_font_size = int(screen_width/font_factor)
		print('Font size: ' + str(self.default_font_size))

		self.team = 0

		self.dir = path.dirname(__file__)

		self.start_list_file = None
		self.start_list_file_time = None
		# self.start_list_observer = Observer()
		# self.start_list_observer.schedule(self, '.')
		# self.start_list_observer.start()

		self.punches_url = None
		self.response_encoding = 'utf-8'
		self.competition_id = None
		self.last_received_punch_id = 0
		self.competition_date = 0
		self.competition_zero_time = 0
		self.use_competition_date = False
		self.use_competition_time = False
		self.fetch_punch_interval = 10
		self.prewarn_codes = {}

		self.sound_enabled = True
		self.default_language = 'sv'
		self.last_sound_time = None
		self.intro_sound_delay = timedelta(seconds=15)
		self.intro_sound = 'sounds/ding.mp3'
		self.test_sound = 'sounds/en/Testing.mp3'
		self.startlist_update_sound = 'sounds/half_ding.mp3'
		self.config_update_sound = 'sounds/half_ding.mp3'

		self.announce_ip = True

		self.team_names = dict()
		self.runners = dict()

		self.config_file = 'prewarning.ini'
		self.config_file_time = None
		self.read_config()

		self.data_file = 'prewarning.dat'
		self.read_data()

		self.punch_queue = Queue()
		self.sound_queue = Queue()

		self.font_size = self.default_font_size
		self.last_item = None

		self.parent = parent

		self.style = Style(parent)
		self.style.configure('Treeview', rowheight=int(self.font_size*1.5))

		self.main_container = Frame(parent)
		self.main_container.pack(side=TOP, fill=BOTH, expand=True)

		self.top_frame = Frame(self.main_container)
		self.prewarn = Label(self.top_frame, text='Förvarning', font=('Arial', self.font_size, 'bold'))
		self.prewarn.pack(anchor=CENTER, side=LEFT, fill=BOTH, expand=True)
		self.clock = Label(self.top_frame, font=('times', self.font_size, 'bold'))
		self.clock.pack(side=RIGHT, fill=BOTH, ipadx=10, expand=False)
		self.tick()
		self.top_frame.pack(side=TOP, fill=X, anchor=N, expand=False)

		self.treeview = Treeview(self.main_container)
		self.treeview['columns'] = ('team', 'leg')
		self.treeview.heading("#0", text='Tid', anchor=W)
		# self.treeview.column("#0", minwidth=int(screen_width/2), width=int(screen_width/2), anchor="w", stretch=False)
		self.treeview.column("#0", anchor=W, stretch=True)
		self.treeview.heading('team', text='Lag', anchor=W)
		self.treeview.column('team', anchor=W, stretch=False)
		self.treeview.heading('leg', text='Sträcka', anchor=W)
		self.treeview.column('leg', minwidth=100, width=100, anchor=W, stretch=False)
		self.treeview.tag_configure('T', font=('Arial', self.font_size, 'bold'))
		self.treeview.pack(side=BOTTOM, fill=BOTH, anchor=N, expand=True)

		self.punch_fetcher = Thread(target=self.fetch_punches)
		self.punch_fetcher.setDaemon(True)

		self.punch_processor = Thread(target=self.process_punches)
		self.punch_processor.setDaemon(True)

		self.sound_player = Thread(target=self.play_sound)
		self.sound_player.setDaemon(True)

		self.file_watcher = Thread(target=self.check_files)
		self.file_watcher.setDaemon(True)

	def notify_ip(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(('8.8.8.8', 0))  # connecting to a UDP address doesn't send packets
		local_ip_address = s.getsockname()[0]
		print(local_ip_address)
		if self.announce_ip:
			for number in local_ip_address.split("."):
				call(['mpg123', '-q', self.add_path('sounds/' + self.default_language + '/' + number + '.mp3')])
		s.close()

	def start(self):
		#self.read_startlist()
		self.punch_fetcher.start()
		self.punch_processor.start()
		self.sound_player.start()
		self.file_watcher.start()

	def add_path(self, file):
		file_path = path.join(self.dir, file)
		return file_path

	def read_config(self):
		config = ConfigParser()
		config.read(self.add_path(self.config_file))

		common = config['Common']
		new_start_list_file = common.get('StartListFile', fallback='startlist.zip')

		punch_source = config['PunchSource']
		self.punches_url = punch_source.get('PunchSourceUrl', fallback='http://roc.olresultat.se/getpunches.asp')
		self.competition_id = punch_source['CompetitionId']
		self.use_competition_date = punch_source.getboolean('UseCompetitionDate', fallback=True)
		self.use_competition_time = punch_source.getboolean('UseCompetitionTime', fallback=True)
		self.fetch_punch_interval = punch_source.getint('FetchPunchesIntervalSeconds', fallback=10)
		self.prewarn_codes = punch_source['PreWarningCodes'].split(',')

		sound = config['Sound']
		self.sound_enabled = sound.getboolean('SoundEnabled', fallback=True)
		self.default_language = sound.get('DefaultLanguage', fallback='sv')
		self.announce_ip = sound.getboolean('AnnounceIp', fallback=True)
		self.intro_sound_delay = timedelta(seconds=sound.getint('IntroSoundDelaySeconds', fallback=10))
		self.intro_sound = sound.get('IntroSoundFile', fallback='sounds/ding.mp3')
		self.test_sound = sound.get('TestSoundFile', fallback='sounds/en/Testing.mp3')

		# print(self.intro_sound)
		call(['mpg123', '-q', self.add_path(self.config_update_sound)])

		if self.config_file_time == None:
			self.notify_ip()

		self.config_file_time = stat(self.add_path(self.config_file)).st_mtime

		if self.start_list_file != new_start_list_file:
			self.start_list_file = new_start_list_file
			self.read_startlist()

	def read_data(self):
		data = ConfigParser()
		data.read(self.add_path(self.data_file))

		punch_source = data['PunchSource']
		self.last_received_punch_id = punch_source.getint('LastReceivedPunchId', fallback=self.last_received_punch_id)

	def write_data(self):
		data = ConfigParser()
		data.read(self.add_path(self.data_file))

		punch_source = data['PunchSource']
		punch_source['LastReceivedPunchId'] = str(self.last_received_punch_id)

		with open(self.add_path(self.data_file), 'w') as datafile:
			data.write(datafile)

	def update_size(self):
		self.style.configure('Treeview', rowheight=int(self.font_size*1.5))
		self.prewarn['font'] = ('Arial', self.font_size, 'bold')
		self.clock['font'] = ('times', self.font_size, 'bold')
		self.treeview.tag_configure('T', font=('Arial', self.font_size, 'bold'))
		if self.last_item is not None:
			self.treeview.see(self.last_item)

	def add_prewarning(self, time, team):
		# last_item = None
		# if self.last_item is not None:
		# 	last_item = self.treeview.item(self.last_item)
		#
		# if last_item is not None:
		# 	if last_item['text'] == time:
		# 		new_value = ''
		# 		for tt in last_item['values']:
		# 			if len(new_value) is not 0:
		# 				new_value += ', '
		# 			new_value += str(tt)
		# 		new_value = '"' + new_value + ', ' + team + '"'
		# 		self.treeview.item(self.last_item, values=new_value)
		# 	else:
		# 		self.last_item = self.treeview.insert('', 'end', text=time, values=team, tags='T')
		# else:
		# 	self.last_item = self.treeview.insert('', 'end', text=time, values=team, tags='T')
		self.last_item = self.treeview.insert('', 'end', text=time, values=team, tags='T')
		self.treeview.see(self.last_item)

	def clear(self):
		self.treeview.delete(*self.treeview.get_children())
		self.last_item = None

	def tick(self):
		# get the current local time from the PC
		new_time = strftime('%H:%M:%S')
		# if time string has changed, update it
		if new_time != self.clock["text"]:
			self.clock["text"] = new_time
		# calls itself every 200 milliseconds
		# to update the time display as needed
		# could use >200 ms, but display gets jerky
		# self.clock.after(200, self.tick)
		self.clock.after(200, self.tick)

	def fetch_punches(self):
		while True:
			date = 0
			time = 0
			if self.use_competition_date:
				date = self.competition_date
			if self.use_competition_time:
				time = self.competition_zero_time
			values = {'unitId': self.competition_id,
						'lastId': self.last_received_punch_id,
						'date': date,
						'time': time}

			url_values = urlencode(values)
			url = self.punches_url + '?' + url_values
			# print(url)
			req = Request(url)
			try:
				response = urlopen(req)
				response_encoding = response.info().get_content_charset()
				if response_encoding is None:
					response_encoding = self.response_encoding
				data = response.read().decode(response_encoding)
				splitlines = data.splitlines()
				if splitlines:
					print(data)
					for line in splitlines:
						punch_dict = dict(zip(('id', 'code', 'card', 'time'), line.split(';')))
						print(punch_dict)
						self.punch_queue.put(punch_dict)
						self.last_received_punch_id = punch_dict['id']
					print(self.last_received_punch_id)
					self.write_data()
			except HTTPError as e:
				print('The server couldn\'t fulfill the request.')
				print('Error code: ', e.code)
			except URLError as e:
				print('We failed to reach a server.')
				print('Reason: ', e.reason)

			sleep(self.fetch_punch_interval)

	def process_punches(self):
		while True:
			punch = self.punch_queue.get()
			print('Processing: ' + punch['card'] + ' from: ' + punch['code'])
			if punch['code'] in self.prewarn_codes:
				runner = self.runners.get(punch['card'])
				if runner is not None:
					time = punch['time'].rpartition(' ')[2]
					bib_number = runner['team_bib_number']
					leg = runner['leg']
					self.add_prewarning(time, (bib_number, leg))
					self.sound_queue.put('sounds/' + self.default_language + '/' + bib_number + '.mp3')
					# if time.endswith('6'):
					# 	self.add_prewarning(time, (str(int(bib_number) + 1), leg))
					# 	self.add_prewarning(time, (str(int(bib_number) + 2), leg))
					# 	self.add_prewarning(time, (str(int(bib_number) + 3), leg))
					# 	self.add_prewarning(time, (str(int(bib_number) + 4), leg))
					# 	self.add_prewarning(time, (str(int(bib_number) + 5), leg))
					# 	self.add_prewarning(time, (str(int(bib_number) + 6), leg))
				else:
					print('Not found')
			else:
				print('Wrong code')

	def play_sound(self):
		while True:
			# print('play_sound')
			sound = self.sound_queue.get()
			if self.sound_enabled:
				# print(self.last_sound_time)
				if self.last_sound_time is None or (datetime.now()-self.last_sound_time).total_seconds() >= self.intro_sound_delay.total_seconds():
					# print(self.intro_sound)
					call(['mpg123', '-q', self.add_path(self.intro_sound)])
				# print(sound)
				call(['mpg123', '-q', self.add_path(sound)])
				self.last_sound_time = datetime.now()
				# print(self.last_sound_time)

	def on_modified(self, event):
		print(event)
		if self.add_path(self.start_list_file) in event.src_path:
			self.read_startlist()
		elif self.add_path('test.txt') in event.src_path:
				print('TEST!')

	def check_files(self):
		while True:
			if stat(self.add_path(self.config_file)).st_mtime != self.config_file_time:
				print('config_file changed!')
				self.read_config()
			if stat(self.add_path(self.start_list_file)).st_mtime != self.start_list_file_time:
				print('start_list_file changed!')
				self.read_startlist()
			sleep(1)

	def read_startlist(self):
		if self.start_list_file.lower().endswith('.zip'):
			archive = ZipFile(self.add_path(self.start_list_file), 'r')
			data = archive.read('SOFTSTRT.XML')
		else:
			f = open(self.add_path(self.start_list_file), 'r', encoding='windows-1252')
			data = f.read()
		startlist = ElementTree.fromstring(data)

		ns = {'ns': 'http://www.orienteering.org/datastandard/3.0'}

		event_id = self.get_data(startlist, 'ns:Event/ns:Id', ns)
		event_name = self.get_data(startlist, 'ns:Event/ns:Name', ns)
		event_date = self.get_data(startlist, 'ns:Event/ns:StartTime/ns:Date', ns)
		organiser_id = self.get_data(startlist, 'ns:Event/ns:Organiser/ns:Id', ns)
		organiser_name = self.get_data(startlist, 'ns:Event/ns:Organiser/ns:Name', ns)

		self.competition_date = event_date

		print('Event: ' + str(event_name) + ' (' + str(event_id) + ') ' + str(event_date))
		print('Organiser: ' + str(organiser_name) + ' (' + str(organiser_id) + ')')

		self.team_names.clear()
		self.runners.clear()

		teams = startlist.findall('ns:ClassStart/ns:TeamStart', ns)
		for team in teams:
			team_name = self.get_data(team, 'ns:Name', ns)
			team_bib_number = self.get_data(team, 'ns:BibNumber', ns)
			self.team_names[team_bib_number] = team_name

			team_members = team.findall('ns:TeamMemberStart', ns)
			for team_member in team_members:
				team_member_id = self.get_data(team_member, 'ns:Person/ns:Id', ns)
				team_member_name_family = self.get_data(team_member, 'ns:Person/ns:Name/ns:Family', ns)
				team_member_name_given = self.get_data(team_member, 'ns:Person/ns:Name/ns:Given', ns)
				team_member_leg = self.get_data(team_member, 'ns:Start/ns:Leg', ns)
				team_member_leg_order = self.get_data(team_member, 'ns:Start/ns:LegOrder', ns)
				team_member_bib_number = self.get_data(team_member, 'ns:Start/ns:BibNumber', ns)
				team_member_control_card = self.get_data(team_member, 'ns:Start/ns:ControlCard', ns)
				if team_member_control_card is not None:
					self.runners[team_member_control_card] = {'id': team_member_id,
																	'family': team_member_name_family,
																	'given': team_member_name_given,
																	'leg': team_member_leg,
																	'leg_order': team_member_leg_order,
																	'team_bib_number': team_bib_number,
																	'bib_number': team_member_bib_number,
																	'control_card': team_member_control_card}
		self.start_list_file_time = stat(self.add_path(self.start_list_file)).st_mtime
		# print('Teams: ' + str(self.team_names))
		# print('Runners: ' + str(self.runners))
		# print(strftime('%H:%M:%S'))

		# print(self.intro_sound)
		call(['mpg123', '-q', self.add_path(self.startlist_update_sound)])

	@staticmethod
	def get_data(element, selector, ns):
		data = element.find(selector, ns)
		if data is not None:
			return data.text
		else:
			return None

	def on_key_press(self, event: Event):
		print('Key symbol: ' + str(event.keysym))
		if event.keysym == 'space' or event.keysym == 'p':
			self.team += 1
			self.add_prewarning(strftime('%H:%M:%S'), (self.team, 1))
			self.sound_queue.put('sounds/' + self.default_language + '/' + str(self.team) + '.mp3')
		if event.keysym == 't':
			self.sound_queue.put(self.test_sound)
		elif event.keysym == 'c':
			self.clear()
		elif event.keysym == 'q':
			exit()
		elif event.keysym == 'plus' or event.keysym == 'KP_Add':
			self.font_size += 1
			print('Font size: ' + str(self.font_size))
			self.update_size()
		elif event.keysym == 'minus' or event.keysym == 'KP_Subtract':
			self.font_size -= 1
			print('Font size: ' + str(self.font_size))
			self.update_size()
		elif event.keysym == '0' or event.keysym == 'KP_0':
			self.font_size = self.default_font_size
			print('Font size: ' + str(self.font_size))
			self.update_size()


def main():
	root = Tk()
	root.attributes('-fullscreen', True)
	# root.geometry("460x800")
	# root.geometry("1366x768")
	# root.geometry("768x1366")
	# root.geometry("768x1200")
	app = App(root)
	root.bind('<Control-Key>', app.on_key_press)
	app.start()
	root.mainloop()

if __name__ == '__main__':
	main()
