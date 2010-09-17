import os, sys
import minixs as mx
import numpy as np
import minixs.info as mxinfo
import wx


HPAD = 10
VPAD = 5

#ID_ = wx.NewId()
ID_DATASET = wx.NewId()
ID_ENERGY = wx.NewId()
ID_NORM = wx.NewId()

ID_CALIB = wx.NewId()
ID_CALIB_LOAD = wx.NewId()
ID_CALIB_VIEW = wx.NewId()

ID_EXPOSURE_LIST = wx.NewId()
ID_EXPOSURE_ADD = wx.NewId()
ID_EXPOSURE_DEL = wx.NewId()

ID_UPDATE_GRAPH = wx.NewId()

WILDCARD_XES = "XES Data Files (*.xes)|*.xes|Data Files (*.dat)|*.dat|Text Files (*.txt)|*.txt"
WILDCARD_CALIB = "Calibration Files (*.calib)|*.calib|Data Files (*.dat)|*.dat|Text Files (*.txt)|*.txt"


class ProcessorApp(wx.App):
  def __init__(self, *args, **kwargs):
    wx.App.__init__(self, *args, **kwargs)

    model = ProcessorModel()
    view = ProcessorFrame(None)
    controller = ProcessorController(view, model)

    view.Show()


class ProcessorFrame(wx.Frame):
  def __init__(self, *args, **kwargs):
    print "frame"
    wx.Frame.__init__(self, *args, **kwargs)

    menu_info = [
        ('&File', [
          ('&Open', wx.ID_OPEN, 'Load XES File'),
          ('&Save', wx.ID_SAVE, 'Save XES File'),
          ('', None, None),
          ('E&xit', wx.ID_EXIT, 'Terminate this program'),
          ]),
        ('&Help', [
          ('&About', wx.ID_ABOUT, 'About this program')
          ]),
        ]
    self.CreateMenuBar(menu_info)
    self.panel = ProcessorPanel(self, wx.ID_ANY)
    self.CreateStatusBar()

  def CreateMenuBar(self, menu_info):
    menubar = wx.MenuBar()

    for menu_name, items in menu_info:
      menu = wx.Menu()

      for label, id, description in items:

        if label == '':
          menu.AppendSeparator()
        
        else:
          menu_item = menu.Append(id, label, description)

      menubar.Append(menu, menu_name)

    self.SetMenuBar(menubar)

class ProcessorPanel(wx.Panel):
  def __init__(self, *args, **kwargs):
    print "Processor Panel"
    wx.Panel.__init__(self, *args, **kwargs)

    self.CreateGUI()

  def CreateGUI(self):
    vbox = wx.BoxSizer(wx.VERTICAL)

    # dataset, energy, I0
    grid = wx.FlexGridSizer(3,2, VPAD, HPAD)

    label = wx.StaticText(self, wx.ID_ANY, "Dataset Name:")
    entry = wx.TextCtrl(self, ID_DATASET)
    grid.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
    grid.Add(entry, 1, wx.EXPAND)
    self.dataset_entry = entry

    label = wx.StaticText(self, wx.ID_ANY, "Incident Energy:")
    entry = wx.TextCtrl(self, ID_ENERGY)
    grid.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
    grid.Add(entry, 1, wx.EXPAND)
    self.energy_entry = entry

    label = wx.StaticText(self, wx.ID_ANY, "Normalization (I0):")
    entry = wx.TextCtrl(self, ID_NORM)
    grid.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
    grid.Add(entry, 1, wx.EXPAND)
    self.norm_entry = entry

    grid.AddGrowableCol(1, 1)

    vbox.Add(grid, 0, wx.EXPAND | wx.BOTTOM, VPAD)

    # calibration matrix info
    hbox = wx.BoxSizer(wx.HORIZONTAL)
    label = wx.StaticText(self, wx.ID_ANY, "Calibration Matrix:")
    hbox.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, HPAD)

    entry = wx.TextCtrl(self, ID_CALIB, style=wx.TE_READONLY)
    hbox.Add(entry, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, HPAD)
    self.calibration_filename_entry = entry

    button = wx.Button(self, ID_CALIB_LOAD, "...")
    hbox.Add(button, 0, wx.RIGHT, HPAD)
    self.load_calibration_button = button

    button = wx.Button(self, ID_CALIB_VIEW, "View")
    hbox.Add(button, 0, 0, HPAD)
    self.view_calibration_button = button

    vbox.Add(hbox, 0, wx.EXPAND | wx.BOTTOM, VPAD)

    # exposure selector
    hbox = wx.BoxSizer(wx.HORIZONTAL)
    label = wx.StaticText(self, wx.ID_ANY, "Spectrum Images:")
    hbox.Add(label, 0, wx.ALIGN_TOP | wx.RIGHT, HPAD)

    listbox = wx.ListBox(self, ID_EXPOSURE_LIST)
    hbox.Add(listbox, 1, wx.EXPAND | wx.RIGHT, HPAD)
    self.listbox = listbox

    vbox2 = wx.BoxSizer(wx.VERTICAL)
    button = wx.Button(self, ID_EXPOSURE_ADD, "Add Files...")
    vbox2.Add(button, 0, wx.BOTTOM, VPAD)
    button = wx.Button(self, ID_EXPOSURE_DEL, "Delete Selected")
    vbox2.Add(button, 0, 0, VPAD)

    hbox.Add(vbox2, 0, 0, HPAD)

    vbox.Add(hbox, 0, wx.EXPAND | wx.BOTTOM, VPAD)

    button = wx.Button(self, ID_UPDATE_GRAPH, "Update Graph")
    vbox.Add(button, 0, wx.EXPAND | wx.BOTTOM, VPAD)

    self.SetSizerAndFit(vbox)
    print "Done"

class ProcessorModel(object):
  def __init__(self):
    self.calibration = mxinfo.CalibrationInfo()
    self.xes = mxinfo.XESInfo()

  def load(self, filename):
    xes = mxinfo.XESInfo()
    xes.load(filename)
    self.xes = xes

    self.load_calibration(xes.calibration_filename)

  def load_calibration(self, calib_filename):
    calibration = mxinfo.CalibrationInfo()
    calibration.load(calib_filename)
    self.calibration = calibration

class ProcessorController(object):
  def __init__(self, view, model):

    self.view = view
    self.model = model

    self.open_directory = ''
    self.save_directory = ''
    self.calib_directory = ''

    self.BindCallbacks()

  def BindCallbacks(self):
    self.view.Bind(wx.EVT_MENU, self.OnMenuOpen, id=wx.ID_OPEN)
    self.view.Bind(wx.EVT_MENU, self.OnMenuSave, id=wx.ID_SAVE)
    self.view.Bind(wx.EVT_MENU, self.OnMenuExit, id=wx.ID_EXIT)
    self.view.Bind(wx.EVT_MENU, self.OnMenuAbout, id=wx.ID_ABOUT)

    self.view.Bind(wx.EVT_BUTTON, self.OnCalibLoad, id=ID_CALIB_LOAD)
    self.view.Bind(wx.EVT_BUTTON, self.OnCalibView, id=ID_CALIB_VIEW)

    self.view.Bind(wx.EVT_BUTTON, self.OnUpdateGraph, id=ID_UPDATE_GRAPH)

  def OnMenuOpen(self, evt):
    if not self.open_directory:
      self.open_directory = self.save_directory

    dlg = wx.FileDialog(self.view, "Select an XES data file to open", self.open_directory, style=wx.FD_OPEN, wildcard=WILDCARD_XES)
    ret = dlg.ShowModal()

    if ret == wx.ID_OK:
      directory = dlg.GetDirectory()
      filename = dlg.GetFilename()

      self.open_directory = directory
      self.model.load(os.path.join(directory, filename))

      # XXX update view

  def OnMenuSave(self, evt):
    if not self.save_directory:
      self.save_directory = self.open_directory
    dlg = wx.FileDialog(self.view, "Select a file to save XES data to", self.save_directory, style=wx.FD_SAVE, wildcard=WILDCARD_XES)
    ret = dlg.ShowModal()

    if ret == wx.ID_OK:
      directory = dlg.GetDirectory()
      filename = dlg.GetFilename()

      self.save_directory = directory
      self.model.save(os.path.join(directory, filename))

  def OnMenuExit(self, evt):
    # XXX check if unsaved changes exist
    self.view.Close()

  def OnMenuAbout(self, evt):
    pass

  def OnCalibLoad(self, evt):
    if not self.calib_directory:
      self.calib_directory = self.open_directory
    if not self.calib_directory:
      self.calib_directory = self.save_directory

    dlg = wx.FileDialog(self.view, "Select a calibration matrix to open", self.calib_directory, style=wx.FD_OPEN, wildcard=WILDCARD_CALIB)
    ret = dlg.ShowModal()

    if ret == wx.ID_OK:
      directory = dlg.GetDirectory()
      filename = dlg.GetFilename()

      self.save_directory = directory
      path = os.path.join(directory, filename)

      self.view.panel.calibration_panel.calibration_filename_entry.SetValue(path)
      self.model.load_calibration(path)

  def OnCalibView(self, evt):
    pass

  def OnUpdateGraph(self, evt):
    pass



if __name__ == "__main__":
  app = ProcessorApp()
  app.MainLoop()
