#!/usr/bin/python

import sys
import time
import sqlite3
import yaml
import feedparser
import webbrowser
from PyQt5.QtWidgets import (QMainWindow, QApplication, QWidget, QAction,
  QTableWidget, QTableWidgetItem,QHeaderView, QAbstractItemView, QLabel,
  QPushButton,QFormLayout,QHBoxLayout,QVBoxLayout,QScrollArea,QGroupBox,
  QLineEdit)
from PyQt5.QtGui import QFont

def loadconfig():
  with open('sources.yaml', 'r') as file:
    config = yaml.safe_load(file)
  return config

def saveconfig(config):
  with open('sources.yaml', 'w') as file:
    yaml.dump(config, file, allow_unicode=True)

# update database & create if not exist
def updatedb():
  # connect to database & create if needed
  con = sqlite3.connect(config['db_file'])
  cur = con.cursor()

  # Create table if not exist
  try:
    cur.execute("SELECT * FROM articles")
  except sqlite3.OperationalError:
    cur.execute("""CREATE TABLE articles(
      source TEXT,
      source_title TEXT,
      title TEXT,
      url TEXT UNIQUE,
      date INTEGER,
      read INTEGER)""")

  for source in config['sources']:
    feed = feedparser.parse(config['sources'][source]['url'])  
    for entry in feed.entries:
      # Insert data if not exist, ignore if not unique (unique columns created above)
      cur.execute("INSERT OR IGNORE INTO articles VALUES (?, ?, ?, ?, ?, ?)",(
        source,
        feed.feed.title,
        entry.title,
        entry.link,
        time.mktime(entry.published_parsed),
        # entry.author,
        # entry.summary,
        0))

      # commit changes, must be after every entry
      con.commit()
  # close database, otherwise you lost all changes
  con.close()

# fetch database data for table
def getdbdata():
  con = sqlite3.connect(config['db_file'])
  cur = con.cursor()
  cur.execute("SELECT source_title, title, url, date, read FROM articles ORDER BY read,date DESC")
  rows = cur.fetchall()
  con.close()
  return rows

def updatentry(url):
  con = sqlite3.connect(config['db_file'])
  cur = con.cursor()
  # comma in (url,) very important
  cur.execute("UPDATE articles SET read=1 WHERE url=?", (url,))
  con.commit()
  con.close()

class TableView(QTableWidget):
  def __init__(self):
    super().__init__()
    rows = getdbdata()
    self.setRowCount(len(rows))
    self.setColumnCount(3)
    # hide row headers
    self.verticalHeader().hide()
    # column titles
    self.setHorizontalHeaderLabels(['Źródło', 'Data', 'Tytuł'])
    # self.setData(rows)
    # first two column resize to content, last fill rest of window
    self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
    self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
    # self.itemClicked.connect(self.clicked)
    self.cellClicked.connect(self.clicked)
    # when clicked select row instead cell
    self.setSelectionBehavior(QAbstractItemView.SelectRows)
  
    for i, row in enumerate(rows):
      src = QTableWidgetItem(row[0])
      dat = QTableWidgetItem(time.strftime('%Y-%m-%d %H:%M', time.localtime(row[3])))
      tit = QTableWidgetItem(row[1])
      # bold if article unread
      font = QFont()
      font.setBold(True)
      if row[4] == 0:
        tit.setFont(font)
      elem = [src,dat,tit]
      for x in range(len(elem)):
        self.setItem(i, x, elem[x])
      # hide url in tooltip
      self.item(i, 2).setToolTip(row[2])

  # click event, open article url in web browser
  def clicked(self, qmodelindex):
    item = self.currentItem()
    # only when clicked third column - article title
    if self.currentColumn() == 2:
      # open url in web browser & update database entry
      webbrowser.open(item.toolTip())
      updatentry(item.toolTip())
      # unbold font in table for item
      font = QFont()
      font.setBold(False)
      item.setFont(font)

class Settings(QWidget):
  def __init__(self, new_config):
    super().__init__()
    self.setFixedSize(300, 400)
    self.setWindowTitle("PyQt RSS – Ustawienia")

    self.new_config = new_config
    
    font = QFont()
    font.setBold(True)

    self.mygroupbox = QGroupBox()
    self.layout = QVBoxLayout()
    # layout for ok/cancel buttons
    self.layout_down = QHBoxLayout()
    self.layout_main = QVBoxLayout()

    # add sources
    self.nameLine = QLineEdit()
    self.urlLine = QLineEdit()
    self.addSourceButton = QPushButton('Dodaj')
    self.addSourceButton.clicked.connect(lambda: self.addSource(self.nameLine.text(), self.urlLine.text()))
    self.addSourceLabel = QLabel('Dodaj źródło:')
    self.addSourceLabel.setFont(font)
    self.addSourceForm = QFormLayout()
    self.addSourceForm.addRow('Nazwa:',self.nameLine)
    self.addSourceForm.addRow('Url:',self.urlLine)
    self.addSourceForm.addRow(self.addSourceButton)
    self.layout_main.addWidget(self.addSourceLabel)
    self.layout_main.addLayout(self.addSourceForm)

    # remove sources
    self.removeLabel = QLabel('Usuń wybrane źródła:')
    self.removeLabel.setFont(font)
    self.layout_main.addWidget(self.removeLabel)
    # add buttons for all sources from config
    for source in self.new_config['sources']:
      self.addRemoveButton(source)

    self.mygroupbox.setLayout(self.layout)
    self.scroll = QScrollArea()
    self.scroll.setWidget(self.mygroupbox)
    self.scroll.setWidgetResizable(True)
    self.layout_main.addWidget(self.scroll)

    # ok/cancel button, disabled
    self.confirmBtn = QPushButton("OK")
    self.confirmBtn.clicked.connect(lambda: self.confirmSettings())
    self.cancel = QPushButton("Anuluj")
    self.cancel.clicked.connect(self.close)
    self.layout_down.addWidget(self.cancel)
    self.layout_down.addWidget(self.confirmBtn)
    self.layout_main.addLayout(self.layout_down)

    self.setLayout(self.layout_main)

  def confirmSettings(self):
    global config
    # remove unknown sources from DB
    con = sqlite3.connect(self.new_config['db_file'])
    cur = con.cursor()
    k = list(self.new_config['sources'].keys())
    q = ', '.join('?' * len(k))
    sqlstr = "DELETE FROM articles WHERE source NOT IN (" + q + ")"
    cur.execute(sqlstr, k)
    con.commit()
    con.close()
    # assign new config to variable & save to file
    config = self.new_config
    saveconfig(self.new_config)
    self.close()

  def addRemoveButton(self, source):
    x = 'Usuń ' + source
    self.removeSourceBtn = QPushButton(x)
    self.removeSourceBtn.setObjectName(source)
    self.removeSourceBtn.setToolTip(self.new_config['sources'][source]['url'])
    self.removeSourceBtn.clicked.connect(lambda: self.removeSource())
    self.layout.addWidget(self.removeSourceBtn)

  def addSource(self, source, url):
    newkey = {source: {'url': url}}
    self.new_config['sources'].update(newkey)
    self.addRemoveButton(source)

  def removeSource(self):
    x = self.sender().objectName()
    self.new_config['sources'].pop(x)
    self.sender().setHidden(True)


class MainWindow(QMainWindow):
  def __init__(self):
    super().__init__()
    self.setWindowTitle('PyQt RSS')
    self.setMinimumSize(650, 800)

    self.menu()
    self.setCentralWidget(TableView())

  def refresh(self):
    updatedb()
    self.setCentralWidget(TableView())

  def menu(self):
    mainMenu = self.menuBar()
    fileMenu = mainMenu.addMenu('Menu')

    refreshButton = QAction('Odśwież', self)
    refreshButton.setShortcut('Ctrl+R')
    refreshButton.triggered.connect(lambda: self.refresh())
    fileMenu.addAction(refreshButton)

    settingButton = QAction('Ustawienia', self)
    settingButton.setShortcut('Ctrl+O')
    settingButton.triggered.connect(lambda: self.settingShow())
    fileMenu.addAction(settingButton)

    exitButton = QAction('Zamknij', self)
    exitButton.setShortcut('Ctrl+Q')
    exitButton.triggered.connect(self.close)
    fileMenu.addAction(exitButton)

  def settingShow(self):
    self.settings = Settings(loadconfig())
    self.settings.show()

if __name__ == "__main__":
  config = loadconfig()
  updatedb()
  app = QApplication(sys.argv)
  window = MainWindow()
  window.show()
  app.exec()
