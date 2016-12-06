__author__ = 'croister'

from tkinter import *
from tkinter.ttk import *
from time import *


class App(Frame):

	def __init__(self, parent):
		Frame.__init__(self, parent)
		self.create_ui()
		self.load_table()
		self.grid(sticky=(N, S, W, E))
		parent.grid_rowconfigure(0, weight=1)
		parent.grid_columnconfigure(0, weight=1)

	def create_ui(self):
		topframe = Frame(self)
		topframe.grid_rowconfigure(0, weight=1)
		topframe.grid_columnconfigure(0, weight=1)
		topframe.grid_columnconfigure(1, weight=0)
		topframe.grid_columnconfigure(2, weight=1)
		prewarn = Label(topframe, text='Förvarning', font=('Arial', 80, 'bold'))
		prewarn.grid(row=0, column=1, sticky=NSEW)
		self.time = ''
		self.clock = Label(topframe, font=('times', 80, 'bold'))
		self.clock.grid(row=0, column=3, sticky=E)
		topframe.grid(sticky=(N, S, W, E))
		style = Style(self)
		style.configure('Treeview', rowheight=100)
		tv = Treeview(self)
		tv['columns'] = 'team'
		tv.heading("#0", text='Tid', anchor='w')
		tv.column("#0", anchor="w", stretch=True)
		tv.heading('team', text='Lag', anchor='w')
		tv.column("team", anchor="w", stretch=True)
		tv.tag_configure('T', font='Arial 80')
		tv.grid(sticky=(N, S, W, E))
		self.treeview = tv
		self.grid_rowconfigure(0, weight=1)
		self.grid_columnconfigure(0, weight=1)

	def load_table(self):
		self.treeview.insert('', 'end', text="09:45:13", values='132', tags='T')
		self.treeview.insert('', 'end', text="09:55:09", values='135', tags='T')
		self.treeview.insert('', 'end', text="10:05:03", values='136', tags='T')
		self.treeview.insert('', 'end', text="10:06:13", values='137', tags='T')
		self.treeview.insert('', 'end', text="10:07:43", values='138', tags='T')
		self.treeview.insert('', 'end', text="10:34:33", values='139', tags='T')
		self.treeview.insert('', 'end', text="10:55:05", values='232', tags='T')
		self.treeview.insert('', 'end', text="11:02:59", values='332', tags='T')

	def tick(self):
		# get the current local time from the PC
		newtime = strftime('%H:%M:%S')
		# if time string has changed, update it
		if newtime != self.time:
			self.time = newtime
			self.clock.config(text=newtime)
		# calls itself every 200 milliseconds
		# to update the time display as needed
		# could use >200 ms, but display gets jerky
		self.clock.after(200, self.tick)


def main():
	root = Tk()
	root.attributes('-fullscreen', True)
	App(root).tick()
	root.mainloop()

if __name__ == '__main__':
	main()
