from minixs.calibrate import Calibration
import wx

from calibrator_controller import CalibratorController
from calibrator_view import CalibratorView
from calibrator_const import *

import minixs.filter as filter
import filter_view

class CalibratorModel(Calibration):
  def __init__(self):
    Calibration.__init__(self)

class CalibratorApp(wx.App):
  def __init__(self, *args, **kwargs):
    wx.App.__init__(self, *args, **kwargs)

    model = CalibratorModel()
    view = CalibratorView(None, ID_MAIN_FRAME, "minIXS Calibrator")
    controller = CalibratorController(view, model)

    view.Show()

def main():
  # register filters
  for f in filter.REGISTRY:
    view_class = getattr(filter_view, f.view_name)
    filter_view.register(f, view_class)

  # run app
  app = CalibratorApp()
  app.MainLoop()
