import os, sys
import minixs as mx
import minixs.info as mxinfo
import wx
import util
from frame import MenuFrame
from matplotlib import cm

HPAD = 10
VPAD = 5

ID_DATASET_NAME     = wx.NewId()
ID_EXPOSURE_LIST    = wx.NewId()
ID_READ_ENERGIES    = wx.NewId()
ID_SELECT_EXPOSURES = wx.NewId()
ID_CLEAR_ENERGIES   = wx.NewId()
ID_CLEAR_EXPOSURES  = wx.NewId()
ID_LOAD_EXPOSURES   = wx.NewId()
ID_DISPERSIVE_DIR   = wx.NewId()
ID_EXPOSURE_SLIDER  = wx.NewId()

ID_IMPORT_XTALS     = wx.NewId()
ID_EXPORT_XTALS     = wx.NewId()

ID_LOAD_SCAN        = wx.NewId()

WILDCARD_CALIB = "Calibration Files (*.calib)|*.calib|Data Files (*.dat)|*.dat|Text Files (*.txt)|*.txt|All Files|*"
WILDCARD_EXPOSURE = "TIF Files (*.tif)|*.tif|All Files|*"
WILDCARD_XTAL = "Crystal Files (*.xtal)|*.xtal|Calibration Files (*.calib)|*.calib|Text Files (*.txt)|*.txt|All Files|*"
WILDCARD_XTAL_EXPORT = "Crystal Files (*.xtal)|*.xtal"
WILDCARD_SCAN = "Scan Files (*.nnnn)|*.????|Text Files (*.txt)|*.txt|All Files|*"

class CalibratorModel(mxinfo.CalibrationInfo):
  def __init__(self):
    mxinfo.CalibrationInfo.__init__(self)

ACTION_NONE = 0
ACTION_RESIZE = 1

RESIZE_L = 0x01
RESIZE_R = 0x02
RESIZE_T = 0x04
RESIZE_B = 0x08

RESIZE_TL = RESIZE_T | RESIZE_L
RESIZE_TR = RESIZE_T | RESIZE_R
RESIZE_BL = RESIZE_B | RESIZE_L
RESIZE_BR = RESIZE_B | RESIZE_R

class ImagePanel(wx.Panel):
  def __init__(self, *args, **kwargs):
    wx.Panel.__init__(self, *args, **kwargs)
    self.bitmap = None
    self.xtals = []

    self.SetEvtHandlerEnabled(True)

    self.bad_pixels = []

    self.Bind(wx.EVT_PAINT, self.OnPaint)
    self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
    self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
    self.Bind(wx.EVT_RIGHT_UP, self.OnRightUp)
    self.Bind(wx.EVT_MOTION, self.OnMotion)

    self.action = ACTION_NONE
    self.resize_dir = 0
    self.resize_xtal = None

    self.coord_cb = None

  def set_pixels(self, pixels):
    if pixels == None:
      self.bitmap = None
    else:
      h,w = pixels.shape
      p = cm.Greys_r(pixels, bytes=True)[:,:,0:3]
      self.bitmap = wx.BitmapFromBuffer(w, h, p.tostring())
    self.Refresh()

  def OnLeftDown(self, evt):
    if self.action == ACTION_NONE:
      x,y = evt.GetPosition()

      off = 4
      resize_dir = 0

      for xtal in self.xtals:
        (x1,y1),(x2,y2) = xtal

        if y1 - off < y < y2 + off:
          if abs(x1 - x) < off:
            resize_dir |= RESIZE_L
          elif abs(x2 - x) < off:
            resize_dir |= RESIZE_R
        if x1 - off < x < x2 + off:
          if abs(y1 - y) < off:
            resize_dir |= RESIZE_T
          elif abs(y2 - y) < off:
            resize_dir |= RESIZE_B

        if resize_dir != 0:
          self.resize_dir = resize_dir
          self.resize_xtal = xtal
          break

      if not self.resize_xtal:
        xtal = [[x,y],[x+1,y+1]]
        self.xtals.append(xtal)
        self.resize_xtal = xtal
        self.resize_dir = RESIZE_BR

      self.action = ACTION_RESIZE

  def OnLeftUp(self, evt):
    if self.action == ACTION_RESIZE:
      (x1,y1), (x2,y2) = self.resize_xtal

      if x2 < x1:
        self.resize_xtal[0][0], self.resize_xtal[1][0] = x2, x1
      if y2 < y1:
        self.resize_xtal[0][1], self.resize_xtal[1][1] = y2, y1

      self.resize_xtal = None
      self.action = ACTION_NONE

  def OnRightUp(self, evt):
    if self.action == ACTION_NONE:
      for xtal in self.xtals:
        x,y = evt.GetPosition()
        (x1,y1), (x2,y2) = xtal

        if x1 <= x <= x2 and y1 <= y <= y2:
          self.xtals.remove(xtal)
          self.Refresh()
          break


  def OnMotion(self, evt):
    x,y = evt.GetPosition()

    if self.coord_cb:
      self.coord_cb(x,y)

    if self.action == ACTION_RESIZE:

      if self.resize_dir & RESIZE_L:
        self.resize_xtal[0][0] = x
      elif self.resize_dir & RESIZE_R:
        self.resize_xtal[1][0] = x
      if self.resize_dir & RESIZE_T:
        self.resize_xtal[0][1] = y
      elif self.resize_dir & RESIZE_B:
        self.resize_xtal[1][1] = y

      self.Refresh()

  def OnPaint(self, evt):
    dc = wx.PaintDC(self)
    if self.bitmap:
      dc.DrawBitmap(self.bitmap, 0, 0)

      dc.SetBrush(wx.Brush('#aa0000', wx.TRANSPARENT))
      dc.SetPen(wx.Pen('#33dd33', 1, wx.DOT_DASH))
      for xtal in self.xtals:
        (x1,y1), (x2,y2) = xtal
        dc.DrawRectangle(x1,y1,x2-x1,y2-y1)


class LoadEnergiesPanel(wx.Panel):
  def __init__(self, *args, **kwargs):
    wx.Panel.__init__(self, *args, **kwargs)

    self.grid = wx.FlexGridSizer(2, 3, HPAD, VPAD)

    # text file
    label = wx.StaticText(self, wx.ID_ANY, 'Text File:')
    self.grid.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)

    self.file_entry = wx.TextCtrl(self)
    self.grid.Add(self.file_entry, 1, wx.EXPAND)

    b = wx.Button(self, ID_LOAD_SCAN, '...')
    self.grid.Add(b)

    # column
    label = wx.StaticText(self, wx.ID_ANY, 'Column:')
    self.grid.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)

    self.combo = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY)
    self.grid.Add(self.combo, 1, wx.EXPAND)

    self.grid.AddGrowableCol(1, 1)

    self.SetSizerAndFit(self.grid)

  def fill_column_names(self, filename):
    columns = util.read_scan_column_names(filename)
    sel = self.combo.GetSelection()
    if columns:
      self.combo.SetItems(columns)

      if sel == -1:
        for i in range(len(columns)):
          if 'energy' in columns[i].lower():
            self.combo.SetSelection(i)
            break
      else:
        self.combo.SetSelection(-1) # force update even if sel is same
        self.combo.SetSelection(sel)

  def get_info(self):
    return (self.file_entry.GetValue(), self.combo.GetSelection())

class LoadEnergiesDialog(wx.Dialog):
  def __init__(self, *args, **kwargs):
    wx.Dialog.__init__(self, *args, **kwargs)

    vbox = wx.BoxSizer(wx.VERTICAL)

    self.panel = LoadEnergiesPanel(self)
    vbox.Add(self.panel, 1, wx.EXPAND | wx.BOTTOM, VPAD)

    hbox = wx.StdDialogButtonSizer()

    b = wx.Button(self, wx.ID_CANCEL, 'Cancel')
    hbox.AddButton(b)

    b = wx.Button(self, wx.ID_OK, 'Add')
    hbox.AddButton(b)

    hbox.Realize()

    vbox.Add(hbox, 0, wx.EXPAND)

    self.SetSizerAndFit(vbox)

  def set_filename(self, filename):
    self.panel.file_entry.SetValue(filename)
    self.panel.fill_column_names(filename)

  def get_info(self):
    return self.panel.get_info()


FILTER_MIN  = 0
FILTER_MAX  = 1
FILTER_LOW  = 2
FILTER_HIGH = 3
FILTER_NBOR = 4
NUM_FILTERS = 5

FILTER_NAMES = [
    'Min Visible',
    'Max Visible',
    'Low Cutoff',
    'High Cutoff',
    'Neighbors'
    ]

FILTER_IDS = [ wx.NewId() for n in FILTER_NAMES ]

class FilterPanel(wx.Panel):
  filter_defaults = [
      (0, True),       # min vis
      (1000, False),   # max vis
      (5, True),       # low cut
      (10000, False),  # high cut
      (2, True)        # neighbors
      ]
  def __init__(self, *args, **kwargs):
    wx.Panel.__init__(self, *args, **kwargs)


    grid = wx.FlexGridSizer(NUM_FILTERS, 2, HPAD, VPAD)
    self.checks = []
    self.spins = []

    for i, name in enumerate(FILTER_NAMES):
      val, enabled = self.filter_defaults[i]
      id = FILTER_IDS[i]
      check = wx.CheckBox(self, id, name)
      check.SetValue(enabled)
      spin = wx.SpinCtrl(self, id, '', max=100000)
      spin.SetValue(val)
      spin.Enable(enabled)

      grid.Add(check)
      grid.Add(spin)

      self.checks.append(check)
      self.spins.append(spin)

    label = wx.StaticText(self, wx.ID_ANY, 'Dispersive Dir.')
    choice = wx.Choice(self, ID_DISPERSIVE_DIR, choices=mx.DIRECTION_NAMES)
    grid.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
    grid.Add(choice)
    self.dispersive_direction = choice

    self.SetSizerAndFit(grid)

  def set_filter_value(self, filter_type, value):
    self.spins[filter_type].SetValue(int(value))

  def set_filter_enabled(self, filter_type, enabled):
    self.checks[filter_type].SetValue(enabled)
    self.spins[filter_type].Enable(enabled)

  def set_filters(self, filters):
    for i, (enabled, val) in enumerate(filters):
      self.checks[i].SetValue(enabled)
      self.spins[i].Enable(enabled)
      self.spins[i].SetValue(val)

  def get_filters(self):
    return [ (self.checks[i].GetValue(), self.spins[i].GetValue()) for i in range(NUM_FILTERS) ]

class ExposurePanel(wx.Panel):
  def __init__(self, *args, **kwargs):
    wx.Panel.__init__(self, *args, **kwargs)

    vbox = wx.BoxSizer(wx.VERTICAL)

    label = wx.StaticText(self, wx.ID_ANY, 'No Exposures Loaded')
    vbox.Add(label, 0, wx.EXPAND | wx.BOTTOM, VPAD)
    self.label = label

    panel = ImagePanel(self, wx.ID_ANY, size=(487,195))
    vbox.Add(panel, 0, wx.EXPAND | wx.BOTTOM, VPAD)
    self.image_panel = panel

    slider = wx.Slider(self, ID_EXPOSURE_SLIDER, 0,0,1)
    slider.Enable(False)
    vbox.Add(slider, 0, wx.EXPAND)
    self.slider = slider

    self.SetSizerAndFit(vbox)

  def SetPixels(self, pixels):
    self.image_panel.set_pixels(pixels)

import wx.lib.mixins.listctrl as listmix
class ExposureList(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
  def __init__(self, *args, **kwargs):
    wx.ListCtrl.__init__(self, *args, **kwargs)
    listmix.ListCtrlAutoWidthMixin.__init__(self)

    self.InsertColumn(0, 'Incident Energy', width=200)
    self.InsertColumn(1, 'Exposure File', width=200)

    self.num_rows = 0
    self.num_energies = 0
    self.num_exposures = 0

  def AppendEnergy(self, energy):
    s = '%.2f' % energy

    if self.num_energies >= self.num_rows:
      self.InsertStringItem(self.num_rows, '')
      self.num_rows += 1

    self.SetStringItem(self.num_energies, 0, s)
    self.EnsureVisible(self.num_energies)

    self.num_energies += 1

  def AppendExposure(self, exposure):
    if self.num_exposures >= self.num_rows:
      self.InsertStringItem(self.num_rows, '')
      self.num_rows += 1

    self.SetStringItem(self.num_exposures, 1, exposure)
    self.EnsureVisible(self.num_exposures)

    self.num_exposures += 1

  def ClearEnergies(self):
    for i in range(self.num_energies):
      self.SetStringItem(i, 0, '')
    self.num_energies = 0

  def ClearExposures(self):
    for i in range(self.num_exposures):
      self.SetStringItem(i, 1, '')
    self.num_exposures = 0

  def GetData(self):
    nr = self.GetItemCount()
    nc = self.GetColumnCount()
    strings = [
        [self.GetItem(i,j).GetText() for j in range(nc)]
        for i in range(nr)
        ]

    energies = []
    files = []
    valid = True
    for row in strings:
      e,f = row
      if e == '' and f == '':
        continue
      if e == '' or f == '':
        valid = False
        continue
      energies.append(float(e))
      files.append(f)

    return (valid, energies, files)

class CalibratorPanel(wx.Panel):
  def __init__(self, *args, **kwargs):
    wx.Panel.__init__(self, *args, **kwargs)

    vbox = wx.BoxSizer(wx.VERTICAL)

    # dataset name box
    hbox = wx.BoxSizer(wx.HORIZONTAL)
    label = wx.StaticText(self, wx.ID_ANY, "Dataset Name: ")
    entry = wx.TextCtrl(self, ID_DATASET_NAME)
    hbox.Add(label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, HPAD)
    hbox.Add(entry, 1, 0 )
    vbox.Add(hbox, 0, wx.EXPAND | wx.BOTTOM, VPAD)
    self.dataset_name = entry

    # exposures list
    listctrl = ExposureList(self, ID_EXPOSURE_LIST,
        style=wx.LC_REPORT|wx.LC_HRULES|wx.LC_VRULES)
    vbox.Add(listctrl, 1, wx.EXPAND | wx.BOTTOM, VPAD)
    self.exposure_list = listctrl

    # buttons to control exposure list
    hbox = wx.BoxSizer(wx.HORIZONTAL)

    button = wx.Button(self, ID_READ_ENERGIES, "Read Energies...")
    hbox.Add(button, 1, wx.EXPAND | wx.RIGHT, HPAD)

    button = wx.Button(self, ID_SELECT_EXPOSURES, "Select Exposures...")
    hbox.Add(button, 1, wx.EXPAND | wx.RIGHT, HPAD)

    button = wx.Button(self, ID_CLEAR_ENERGIES, "Clear Energies")
    hbox.Add(button, 1, wx.EXPAND | wx.RIGHT, HPAD)

    button = wx.Button(self, ID_CLEAR_EXPOSURES, "Clear Exposures")
    hbox.Add(button, 1, wx.EXPAND)

    vbox.Add(hbox, 0, wx.EXPAND | wx.BOTTOM, VPAD)

    # load exposures button
    button = wx.Button(self, ID_LOAD_EXPOSURES, "Load Exposures")
    vbox.Add(button, 0, wx.EXPAND | wx.BOTTOM, VPAD)
   
    # add filters and image view
    hbox = wx.BoxSizer(wx.HORIZONTAL)

    panel = FilterPanel(self, wx.ID_ANY)
    hbox.Add(panel, 0, wx.RIGHT, HPAD)
    self.filter_panel = panel

    panel = ExposurePanel(self, wx.ID_ANY)
    hbox.Add(panel, 1)
    self.exposure_panel = panel

    vbox.Add(hbox, 0, wx.EXPAND)

    self.SetSizerAndFit(vbox)

class CalibratorFrame(MenuFrame):
  def __init__(self, *args, **kwargs):
    kwargs['menu_info'] = [
        ('&File', [
          ('&Open', wx.ID_OPEN, 'Load Calibration'),
          ('&Save', wx.ID_SAVE, 'Save Calibration'),
          ('', None, None), # separator
          ('&Import Crystals', ID_IMPORT_XTALS, 'Import Crystals'),
          ('&Export Crystals', ID_EXPORT_XTALS, 'Export Crystals'),
          ('', None, None), # separator
          ('E&xit', wx.ID_EXIT, 'Terminate this program'),
          ]),
        ('&Help', [
          ('&About', wx.ID_ABOUT, 'About this program')
          ]),
        ]
    MenuFrame.__init__(self, *args, **kwargs)
    self.CreateStatusBar()

    box = wx.BoxSizer(wx.VERTICAL)
    self.panel = CalibratorPanel(self, wx.ID_ANY)
    box.Add(self.panel, 1, wx.EXPAND | wx.ALL, VPAD)

    self.SetSizerAndFit(box)

class CalibratorController(object):
  CHANGED_FILTERS = 1
  CHANGED_EXPOSURES = 2
  CHANGED_SELECTED_EXPOSURE = 4

  def __init__(self, view, model):
    self.view = view
    self.model = model

    self.changed_flag = 0
    self.changed_timeout = None

    self.selected_exposure = 1
    self.exposures = []
    self.energies = []

    self.dialog_dirs = {
        'last': '',
        }

    self.BindCallbacks()

  def BindCallbacks(self):
    callbacks = [
        (wx.EVT_MENU, [
          (wx.ID_EXIT, self.OnExit),
          (wx.ID_OPEN, self.OnOpen),
          (wx.ID_SAVE, self.OnSave),
          (ID_IMPORT_XTALS, self.OnImportXtals),
          (ID_EXPORT_XTALS, self.OnExportXtals),
          (wx.ID_ABOUT, self.OnAbout),
          ]),
        (wx.EVT_TEXT, [
          (ID_DATASET_NAME, self.OnDatasetName),
          ]),
        (wx.EVT_BUTTON, [
          (ID_READ_ENERGIES, self.OnReadEnergies),
          (ID_CLEAR_ENERGIES, self.OnClearEnergies),
          (ID_SELECT_EXPOSURES, self.OnSelectExposures),
          (ID_CLEAR_EXPOSURES, self.OnClearExposures),
          (ID_LOAD_EXPOSURES, self.OnLoadExposures),
          ]),
        (wx.EVT_SLIDER, [
          (ID_EXPOSURE_SLIDER, self.OnExposureSlider),
          ]),
        ]

    for event, bindings in callbacks:
      for id, callback in bindings:
        self.view.Bind(event, callback, id=id)

    for id in FILTER_IDS:
      self.view.Bind(wx.EVT_SPINCTRL, self.OnFilterSpin, id=id)
      self.view.Bind(wx.EVT_CHECKBOX, self.OnFilterCheck, id=id)

  def model_to_view(self):
    self.view.panel.dataset_name.SetValue(self.model.dataset_name)

    self.view.panel.filter_panel.dispersive_direction.SetSelection(self.model.dispersive_direction)

    for f in self.model.exposure_files:
      self.view.panel.exposure_list.AppendExposure(f)
    for e in self.model.energies:
      self.view.panel.exposure_list.AppendEnergy(e)

    filters = [(False, val) for enabled,val in self.view.panel.filter_panel.filter_defaults]

    for name, val in self.model.filters:
      i = FILTER_NAMES.index(name)
      filters[i] = (True, val)

    self.view.panel.filter_panel.set_filters(filters)

  def view_to_model(self):
    self.model.dataset_name = self.view.panel.dataset_name.GetValue()
    self.model.dispersive_direction = self.view.panel.filter_panel.dispersive_direction.GetSelection()
    valid, energies, exposure_files = self.view.panel.exposure_list.GetData()
    if valid:
      self.model.energies = energies
      self.model.exposure_files = exposure_files
    else:
      raise ValueError("Number of energies and exposures in list differ")

    self.model.filters = []
    filters = self.view.panel.filter_panel.get_filters()
    for i, (enabled, val) in enumerate(filters):
      if enabled:
        self.model.filters.append( (FILTER_NAMES[i], val) )


  def OnOpen(self, evt):
    filename = self.FileDialog(
        'open',
        'Select a calibration file to open',
        wildcard=WILDCARD_CALIB
        )

    if (filename):
      self.model.load(filename)
      self.model_to_view()
      self.changed(self.CHANGED_EXPOSURES)

  def OnSave(self, evt):
    filename = self.FileDialog(
        'save',
        'Select file to save calibration to',
        wildcard=WILDCARD_CALIB,
        save=True
        )
    if filename:
      self.view_to_model()
      self.model.save(filename)

  def OnImportXtals(self, evt):
    filename = self.FileDialog(
        'xtals',
        'Select file to import crystals from',
        wildcard=WILDCARD_XTAL,
        )

    #XXX implement

  def OnExportXtals(self, evt):
    filename = self.FileDialog(
        'xtals',
        'Select file to export crystals to',
        wildcard=WILDCARD_XTAL_EXPORT
        )

    #XXX implement

  def OnExit(self, evt):
    self.view.Close(True)

  def OnAbout(self, evt):
    pass

  def OnDatasetName(self, evt):
    self.model.dataset_name = evt.GetString()

  def OnReadEnergies(self, evt):
    dlg = LoadEnergiesDialog(self.view)
    dlg.Bind(wx.EVT_BUTTON, self.OnLoadScan, id=ID_LOAD_SCAN)
    self.scan_dialog = dlg
    ret = dlg.ShowModal()

    if ret == wx.ID_OK:
      filename, column = dlg.get_info()
      energies = mx.read_scan_info(filename, [column])[0]

      for e in energies:
        self.view.panel.exposure_list.AppendEnergy(e)

      self.changed(self.CHANGED_EXPOSURES)

    dlg.Destroy()
    self.scan_dialog = None

  def OnLoadScan(self, evt):
    filename = self.FileDialog(
        'scan',
        'Select a text file',
        wildcard=WILDCARD_SCAN
        )

    if filename:
      self.scan_dialog.set_filename(filename)

  def OnClearEnergies(self, evt):
    self.view.panel.exposure_list.ClearEnergies()
    self.changed(self.CHANGED_EXPOSURES)

  def OnSelectExposures(self, evt):
    filenames = self.FileDialog(
        'exposures',
        'Select Exposure Files',
        wildcard=WILDCARD_EXPOSURE,
        multiple=True
        )
    for f in filenames:
      self.view.panel.exposure_list.AppendExposure(f)

    if filenames:
      self.changed(self.CHANGED_EXPOSURES)

  def FileDialog(self, type, title, wildcard='', save=False, multiple=False):
    """
    Show a file dialog and return selected path(s)
    """
    if type not in self.dialog_dirs.keys() or not self.dialog_dirs[type]:
      self.dialog_dirs[type] = self.dialog_dirs['last']

    style = 0
    if save:
      style |= wx.FD_SAVE
    else:
      style |= wx.FD_OPEN
    if multiple:
      style |= wx.FD_MULTIPLE

    dlg = wx.FileDialog(self.view, title,
        self.dialog_dirs[type],
        wildcard=wildcard,
        style=style)

    ret = dlg.ShowModal()

    paths = []
    if ret == wx.ID_OK:
      directory = dlg.GetDirectory()
      self.dialog_dirs[type] = self.dialog_dirs['last'] = directory
      filenames = dlg.GetFilenames()

      paths = [os.path.join(directory, f) for f in filenames]

    dlg.Destroy()

    if not paths:
      return None

    if multiple:
      return paths
    else:
      return paths[0]

  def OnClearExposures(self, evt):
    self.view.panel.exposure_list.ClearExposures()
    self.changed(self.CHANGED_EXPOSURES)

  def OnLoadExposures(self, evt):
    self.changed(self.CHANGED_EXPOSURES)

  def OnFilterSpin(self, evt):
    self.filters= self.view.panel.filter_panel.get_filters()
    self.changed(self.CHANGED_FILTERS)

  def OnFilterCheck(self, evt):
    i = FILTER_IDS.index(evt.Id)
    self.view.panel.filter_panel.set_filter_enabled(i, evt.Checked())
    self.filters = self.view.panel.filter_panel.get_filters()
    self.changed(self.CHANGED_FILTERS)

  def OnExposureSlider(self, evt):
    i = evt.GetInt()
    self.SelectExposure(i)

  def SelectExposure(self, num):
    num_exposures = len(self.exposures)
    if num > num_exposures:
      num = num_exposures

    self.selected_exposure = num
    self.changed(self.CHANGED_SELECTED_EXPOSURE)

  def changed(self, flag):
    self.changed_flag |= flag
    delay = 1000./30.

    if self.changed_timeout is None:
      self.changed_timeout = wx.CallLater(delay, self.OnChangeTimeout)
    elif not self.changed_timeout.IsRunning():
      self.changed_timeout.Restart(delay)

  def OnChangeTimeout(self):
    print "Changed: ", self.changed_flag

    if self.changed_flag & self.CHANGED_EXPOSURES:

      # update list of exposures
      valid, self.energies, self.exposures = self.view.panel.exposure_list.GetData()

      # set status text to indicate wheterh list is valid or not
      if not valid:
        self.view.SetStatusText("Exposure List Invalid")
      else:
        self.view.SetStatusText("")

      # update slider
      num_exposures = len(self.exposures)
      if num_exposures <= 1:
        self.view.panel.exposure_panel.slider.Enable(False)
        self.view.panel.exposure_panel.slider.SetRange(0,1)
        self.view.panel.exposure_panel.slider.SetValue(0)
      else:
        self.view.panel.exposure_panel.slider.Enable(True)
        self.view.panel.exposure_panel.slider.SetRange(1,num_exposures)

      # mark calibration matrix as invalid
      self.calib_invalid = True

    if self.changed_flag & (self.CHANGED_EXPOSURES|self.CHANGED_SELECTED_EXPOSURE):
      # get index of selected exposure and ensure it is within range
      i = self.selected_exposure - 1
      if i >= len(self.exposures):
        i = len(self.exposures) - 1
      if i == -1:
        # no exposures
        self.view.panel.exposure_panel.label.SetLabel("No Exposures Loaded...")
        self.view.panel.exposure_panel.SetPixels(None)
      else:
        filename = self.exposures[i]
        energy = self.energies[i]

        e = mx.Exposure(filename)
        self.view.panel.exposure_panel.SetPixels(e.pixels)

        text = '%d/%d %s - %.2f eV' % (self.selected_exposure, len(self.exposures), os.path.basename(filename), energy)
        self.view.panel.exposure_panel.label.SetLabel(text)

    if self.changed_flag & self.CHANGED_FILTERS:
      pass

    self.changed_flag = 0

class CalibratorApp(wx.App):
  def __init__(self, *args, **kwargs):
    wx.App.__init__(self, *args, **kwargs)

    model = CalibratorModel()
    view = CalibratorFrame(None, wx.ID_ANY, "minIXS Calibrator")
    controller = CalibratorController(view, model)

    view.Show()

if __name__ == "__main__":
  app = CalibratorApp()
  app.MainLoop()
